from pathlib import Path


def test_main_window_uses_workbench_and_settings_pages():
    source = Path("app/main.py").read_text("utf-8")

    assert "class WorkbenchPage" in source
    assert "class SettingsPage" in source
    assert "class LogPage" in source
    assert "class AddTaskDialog" in source
    assert "TableWidget" in source
    assert "操作" in source
    assert "retry_task(" in source
    assert "delete_task(" in source
    assert "TaskRunner(logger)" in source
    assert 'addSubInterface(self.workbench_page, FluentIcon.ROBOT, "工作台")' in source
    assert 'addSubInterface(self.settings_page, FluentIcon.SETTING, "设置"' in source
    assert 'addSubInterface(self.log_page, FluentIcon.DOCUMENT, "日志")' in source
    assert '"流程待接入"' not in source
    assert '"改写要求"' not in source
    assert '"开始生成"' not in source
    assert '"执行流程"' not in source
    assert '"任务选项"' not in source
    assert '"添加任务"' in source
    assert '"运行日志"' not in source
    assert "self.run_log" not in source
    assert "logger.info" in source
    assert "add_task(" in source
    assert "QFileDialog.getOpenFileName" in source
    assert "QFileDialog.getExistingDirectory" not in source
    assert "class TaskPage" not in source
    assert '"复刻任务"' not in source
