import logging
import sys
from datetime import date
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QFrame,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    SwitchButton,
    TableWidget,
    TextEdit,
    setTheme,
    Theme,
)

from app.settings import load_settings, save_settings
from app.task_runner import TaskRunner
from app.tasks import add_task, delete_task, list_tasks, pause_active_tasks, resume_paused_tasks, retry_task

APP_NAME = "TK爆款复刻"


def setup_logging() -> logging.Logger:
    log_dir = Path.cwd() / ".data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / f"{date.today():%Y-%m-%d}.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger(APP_NAME)


def set_combo_text(combo: ComboBox, text: str) -> None:
    index = combo.findText(text)
    if index >= 0:
        combo.setCurrentIndex(index)


def add_form_grid(layout: QVBoxLayout, rows):
    grid = QGridLayout()
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(8)
    for index, (label, widget) in enumerate(rows):
        row, col = divmod(index, 2)
        col *= 2
        grid.addWidget(BodyLabel(label), row, col)
        grid.addWidget(widget, row, col + 1)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(3, 1)
    layout.addLayout(grid)


def add_path_row(layout: QVBoxLayout, label: str, field: LineEdit, button: PushButton) -> None:
    row = QHBoxLayout()
    row.addWidget(BodyLabel(label))
    row.addWidget(field, 1)
    row.addWidget(button)
    layout.addLayout(row)


def set_number_text(widget: LineEdit, value) -> None:
    widget.setText(str(value))


def int_text(widget: LineEdit) -> int:
    return int(widget.text().strip())


def float_text(widget: LineEdit) -> float:
    return float(widget.text().strip())


class WorkbenchPage(QFrame):
    def __init__(self, settings, logger, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.logger = logger
        self.setObjectName("workbenchPage")

        add_button = PrimaryPushButton(FluentIcon.ADD, "添加任务")
        add_button.clicked.connect(self.open_add_dialog)
        refresh_button = PushButton(FluentIcon.SYNC, "刷新")
        refresh_button.clicked.connect(self.refresh_tasks)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(refresh_button)
        actions.addWidget(add_button)

        self.table = TableWidget(self)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["任务ID", "状态", "当前步骤", "爆款视频", "原电影", "输出目录", "更新时间", "操作"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        layout.addLayout(actions)
        layout.addWidget(self.table, 1)
        self.refresh_tasks()

    def open_add_dialog(self) -> None:
        dialog = AddTaskDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            task = add_task(dialog.viral_video.text().strip(), dialog.source_movie.text().strip())
            self.logger.info("task added: %s", task["id"])
            self.refresh_tasks()
            InfoBar.success(
                title="任务已添加",
                content=f".data/tasks/{task['id']}.json",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2200,
                parent=self.window(),
            )

    def refresh_tasks(self) -> None:
        tasks = list_tasks()
        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [
                task.get("id", ""),
                task.get("status", ""),
                task.get("current_step", ""),
                task.get("viral_video", ""),
                task.get("source_movie", ""),
                task.get("output_dir", ""),
                task.get("updated_at", ""),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
            self.table.setCellWidget(row, 7, self.operation_cell(task.get("id", "")))

    def operation_cell(self, task_id: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        retry = PushButton("重试")
        retry.clicked.connect(lambda: self.retry_selected_task(task_id))
        delete = PushButton("删除")
        delete.clicked.connect(lambda: self.delete_selected_task(task_id))
        layout.addWidget(retry)
        layout.addWidget(delete)
        layout.addStretch(1)
        return widget

    def retry_selected_task(self, task_id: str) -> None:
        retry_task(task_id)
        self.logger.info("task retried: %s", task_id)
        self.refresh_tasks()

    def delete_selected_task(self, task_id: str) -> None:
        delete_task(task_id)
        self.logger.info("task deleted: %s", task_id)
        self.refresh_tasks()


class AddTaskDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加任务")
        self.resize(720, 180)
        self.viral_video = LineEdit()
        self.viral_video.setPlaceholderText("爆款视频文件路径")
        self.source_movie = LineEdit()
        self.source_movie.setPlaceholderText("原电影文件路径")
        viral_button = PushButton(FluentIcon.FOLDER, "选择")
        viral_button.clicked.connect(lambda: self.choose_file(self.viral_video))
        source_button = PushButton(FluentIcon.FOLDER, "选择")
        source_button.clicked.connect(lambda: self.choose_file(self.source_movie))

        add_button = PrimaryPushButton(FluentIcon.ADD, "添加任务")
        add_button.clicked.connect(self.accept_if_ready)
        cancel_button = PushButton("取消")
        cancel_button.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        add_path_row(layout, "爆款视频", self.viral_video, viral_button)
        add_path_row(layout, "原电影", self.source_movie, source_button)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(cancel_button)
        actions.addWidget(add_button)
        layout.addLayout(actions)

    def choose_file(self, target: LineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择视频", "", "Video Files (*.mp4 *.mov *.mkv *.avi);;All Files (*)")
        if path:
            target.setText(path)

    def accept_if_ready(self) -> None:
        if not self.viral_video.text().strip() or not self.source_movie.text().strip():
            InfoBar.warning(
                title="缺少路径",
                content="请选择爆款视频和原电影。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2200,
                parent=self,
            )
            return
        self.accept()

class SettingsPage(QFrame):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("settingsPage")

        self.llm_provider = ComboBox()
        self.llm_provider.addItems(["Gemini网关", "OpenAI兼容", "DeepSeek", "通义千问", "自定义"])
        self.llm_model = LineEdit()
        self.llm_model.setPlaceholderText("模型名，例如 gpt-4.1-mini")
        self.llm_api_key = LineEdit()
        self.llm_api_key.setPlaceholderText("API Key")
        self.llm_base_url = LineEdit()
        self.llm_base_url.setPlaceholderText("Base URL")

        llm_card = CardWidget()
        llm_layout = QVBoxLayout(llm_card)
        llm_layout.setContentsMargins(20, 18, 20, 20)
        llm_layout.setSpacing(12)
        llm_layout.addWidget(SubtitleLabel("LLM模型设置"))
        add_form_grid(llm_layout, [
            ("Provider", self.llm_provider),
            ("模型", self.llm_model),
            ("API Key", self.llm_api_key),
            ("Base URL", self.llm_base_url),
        ])

        self.refresh_gemini = SwitchButton()
        self.refresh_gemini.setText("强制重新提取Gemini文案")
        self.min_word_overlap = LineEdit()

        tts_card = CardWidget()
        tts_layout = QVBoxLayout(tts_card)
        tts_layout.setContentsMargins(20, 18, 20, 20)
        tts_layout.setSpacing(12)
        tts_layout.addWidget(SubtitleLabel("TTS分离设置"))
        tts_layout.addWidget(self.refresh_gemini)
        add_form_grid(tts_layout, [("最小词重合率", self.min_word_overlap)])

        self.vad_threshold = LineEdit()
        self.min_speech_ms = LineEdit()
        self.min_silence_ms = LineEdit()

        vad_card = CardWidget()
        vad_layout = QVBoxLayout(vad_card)
        vad_layout.setContentsMargins(20, 18, 20, 20)
        vad_layout.setSpacing(12)
        vad_layout.addWidget(SubtitleLabel("VAD参数设置"))
        add_form_grid(vad_layout, [
            ("阈值", self.vad_threshold),
            ("最短语音(ms)", self.min_speech_ms),
            ("最短静音(ms)", self.min_silence_ms),
        ])

        self.target_language = ComboBox()
        self.target_language.addItems(["Chinese", "English", "Japanese", "Korean"])
        self.rewrite_style = TextEdit()
        self.rewrite_style.setFixedHeight(72)
        self.max_segment_seconds = LineEdit()
        self.max_gap_ms = LineEdit()

        rewrite_card = CardWidget()
        rewrite_layout = QVBoxLayout(rewrite_card)
        rewrite_layout.setContentsMargins(20, 18, 20, 20)
        rewrite_layout.setSpacing(12)
        rewrite_layout.addWidget(SubtitleLabel("文案改写设置"))
        add_form_grid(rewrite_layout, [("目标语言", self.target_language)])
        rewrite_layout.addWidget(BodyLabel("改写风格"))
        rewrite_layout.addWidget(self.rewrite_style)
        add_form_grid(rewrite_layout, [
            ("最大分段秒数", self.max_segment_seconds),
            ("最大断句间隔(ms)", self.max_gap_ms),
        ])

        self.minimax_group_id = LineEdit()
        self.minimax_group_id.setPlaceholderText("Group ID")
        self.minimax_api_key = LineEdit()
        self.minimax_api_key.setPlaceholderText("API Key")
        self.minimax_base_url = LineEdit()
        self.minimax_model = LineEdit()
        self.voice_id = LineEdit()
        self.voice_id.setPlaceholderText("音色 ID")
        self.voice_speed = LineEdit()
        self.voice_volume = LineEdit()
        self.voice_pitch = LineEdit()
        self.audio_format = ComboBox()
        self.audio_format.addItems(["mp3", "wav", "pcm"])

        minimax_card = CardWidget()
        minimax_layout = QVBoxLayout(minimax_card)
        minimax_layout.setContentsMargins(20, 18, 20, 20)
        minimax_layout.setSpacing(12)
        minimax_layout.addWidget(SubtitleLabel("Minimax音频设置"))
        add_form_grid(minimax_layout, [
            ("Base URL", self.minimax_base_url),
            ("Group ID", self.minimax_group_id),
            ("API Key", self.minimax_api_key),
            ("模型", self.minimax_model),
            ("音色 ID", self.voice_id),
            ("语速", self.voice_speed),
            ("音量", self.voice_volume),
            ("音调", self.voice_pitch),
            ("格式", self.audio_format),
        ])

        self.rewrite_dir = LineEdit()
        self.match_dir = LineEdit()
        self.default_output_dir = LineEdit()
        self.default_output_dir.setPlaceholderText("默认输出目录")
        self.whisper_model = LineEdit()
        self.vad_model = LineEdit()

        path_card = CardWidget()
        path_layout = QVBoxLayout(path_card)
        path_layout.setContentsMargins(20, 18, 20, 20)
        path_layout.setSpacing(12)
        path_layout.addWidget(SubtitleLabel("路径设置"))
        add_form_grid(path_layout, [
            ("文案洗稿目录", self.rewrite_dir),
            ("镜头匹配目录", self.match_dir),
            ("默认输出目录", self.default_output_dir),
            ("Whisper模型", self.whisper_model),
            ("VAD模型", self.vad_model),
        ])

        self.gpu_enabled = SwitchButton()
        self.gpu_enabled.setText("启用CUDA镜头匹配")

        match_card = CardWidget()
        match_layout = QVBoxLayout(match_card)
        match_layout.setContentsMargins(20, 18, 20, 20)
        match_layout.setSpacing(12)
        match_layout.addWidget(SubtitleLabel("镜头匹配设置"))
        add_form_grid(match_layout, [("GPU加速", self.gpu_enabled)])

        self.keep_temp = SwitchButton()
        self.keep_temp.setText("保留中间文件")
        self.video_codec = LineEdit()
        self.audio_codec = LineEdit()

        compose_card = CardWidget()
        compose_layout = QVBoxLayout(compose_card)
        compose_layout.setContentsMargins(20, 18, 20, 20)
        compose_layout.setSpacing(12)
        compose_layout.addWidget(SubtitleLabel("内容拼接设置"))
        compose_layout.addWidget(self.keep_temp)
        add_form_grid(compose_layout, [
            ("视频编码", self.video_codec),
            ("音频编码", self.audio_codec),
        ])

        save = PrimaryPushButton(FluentIcon.SAVE, "保存设置")
        save.clicked.connect(self.show_saved)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        for card in [llm_card, tts_card, vad_card, rewrite_card, minimax_card, path_card, match_card, compose_card]:
            content_layout.addWidget(card)
        content_layout.addWidget(save, 0, Qt.AlignmentFlag.AlignRight)
        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        layout.addWidget(scroll, 1)
        self.load_to_form(settings)

    def load_to_form(self, settings):
        set_combo_text(self.llm_provider, settings["llm"]["provider"])
        self.llm_model.setText(settings["llm"]["model"])
        self.llm_api_key.setText(settings["llm"]["api_key"])
        self.llm_base_url.setText(settings["llm"]["base_url"])
        self.refresh_gemini.setChecked(settings["tts_extract"]["refresh_gemini"])
        set_number_text(self.min_word_overlap, settings["tts_extract"]["min_word_overlap"])
        set_number_text(self.vad_threshold, settings["vad"]["threshold"])
        set_number_text(self.min_speech_ms, settings["vad"]["min_speech_ms"])
        set_number_text(self.min_silence_ms, settings["vad"]["min_silence_ms"])
        set_combo_text(self.target_language, settings["rewrite"]["target_language"])
        self.rewrite_style.setPlainText(settings["rewrite"]["style"])
        set_number_text(self.max_segment_seconds, settings["rewrite"]["max_segment_seconds"])
        set_number_text(self.max_gap_ms, settings["rewrite"]["max_gap_ms"])
        self.minimax_base_url.setText(settings["minimax"]["base_url"])
        self.minimax_group_id.setText(settings["minimax"]["group_id"])
        self.minimax_api_key.setText(settings["minimax"]["api_key"])
        self.minimax_model.setText(settings["minimax"]["model"])
        self.voice_id.setText(settings["minimax"]["voice_id"])
        set_number_text(self.voice_speed, settings["minimax"]["speed"])
        set_number_text(self.voice_volume, settings["minimax"]["volume"])
        set_number_text(self.voice_pitch, settings["minimax"]["pitch"])
        set_combo_text(self.audio_format, settings["minimax"]["audio_format"])
        self.rewrite_dir.setText(settings["paths"]["rewrite_dir"])
        self.match_dir.setText(settings["paths"]["video_match_dir"])
        self.default_output_dir.setText(settings["paths"]["output_dir"])
        self.whisper_model.setText(settings["paths"]["whisper_model"])
        self.vad_model.setText(settings["paths"]["vad_model"])
        self.gpu_enabled.setChecked(settings["video_match"].get("gpu_enabled", False))
        self.keep_temp.setChecked(settings["compose"]["keep_temp"])
        self.video_codec.setText(settings["compose"]["video_codec"])
        self.audio_codec.setText(settings["compose"]["audio_codec"])

    def form_settings(self):
        settings = {
            "paths": {
                "rewrite_dir": self.rewrite_dir.text(),
                "video_match_dir": self.match_dir.text(),
                "output_dir": self.default_output_dir.text(),
                "whisper_model": self.whisper_model.text(),
                "vad_model": self.vad_model.text(),
            },
            "llm": {
                "provider": self.llm_provider.currentText(),
                "model": self.llm_model.text(),
                "base_url": self.llm_base_url.text(),
                "api_key": self.llm_api_key.text(),
            },
            "tts_extract": {
                "refresh_gemini": self.refresh_gemini.isChecked(),
                "min_word_overlap": float_text(self.min_word_overlap),
            },
            "rewrite": {
                "target_language": self.target_language.currentText(),
                "style": self.rewrite_style.toPlainText(),
                "max_segment_seconds": int_text(self.max_segment_seconds),
                "max_gap_ms": int_text(self.max_gap_ms),
            },
            "vad": {
                "threshold": float_text(self.vad_threshold),
                "min_speech_ms": int_text(self.min_speech_ms),
                "min_silence_ms": int_text(self.min_silence_ms),
            },
            "video_match": {
                "gpu_enabled": self.gpu_enabled.isChecked(),
            },
            "minimax": {
                "base_url": self.minimax_base_url.text(),
                "group_id": self.minimax_group_id.text(),
                "api_key": self.minimax_api_key.text(),
                "model": self.minimax_model.text(),
                "voice_id": self.voice_id.text(),
                "speed": float_text(self.voice_speed),
                "volume": float_text(self.voice_volume),
                "pitch": int_text(self.voice_pitch),
                "audio_format": self.audio_format.currentText(),
            },
            "compose": {
                "keep_temp": self.keep_temp.isChecked(),
                "video_codec": self.video_codec.text(),
                "audio_codec": self.audio_codec.text(),
            },
        }
        return settings

    def show_saved(self):
        self.settings.clear()
        self.settings.update(self.form_settings())
        save_settings(self.settings)
        InfoBar.success(
            title="已保存",
            content=".data/settings.json 已更新。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2200,
            parent=self.window(),
        )


class LogPage(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logPage")
        self.log_path = Path.cwd() / ".data" / "logs" / f"{date.today():%Y-%m-%d}.log"
        self.output = TextEdit()
        self.output.setReadOnly(True)
        refresh = PushButton(FluentIcon.SYNC, "刷新")
        refresh.clicked.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        layout.addWidget(BodyLabel(str(self.log_path)))
        layout.addWidget(self.output, 1)
        layout.addWidget(refresh, 0, Qt.AlignmentFlag.AlignRight)
        self.refresh()

    def refresh(self) -> None:
        self.output.setPlainText(self.log_path.read_text("utf-8") if self.log_path.exists() else "")


class MainWindow(FluentWindow):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.setWindowTitle(APP_NAME)
        self.resize(980, 680)
        self.settings = load_settings()
        resume_paused_tasks()
        self.runner = TaskRunner(logger)
        self.runner.start()

        self.workbench_page = WorkbenchPage(self.settings, self.logger, self)
        self.settings_page = SettingsPage(self.settings, self)
        self.log_page = LogPage(self)

        self.addSubInterface(self.workbench_page, FluentIcon.ROBOT, "工作台")
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, "设置")
        self.addSubInterface(self.log_page, FluentIcon.DOCUMENT, "日志")

    def closeEvent(self, event):
        pause_active_tasks()
        self.runner.stop()
        super().closeEvent(event)


def main():
    logger = setup_logging()
    logger.info("app started")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    setTheme(Theme.AUTO)

    window = MainWindow(logger)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
