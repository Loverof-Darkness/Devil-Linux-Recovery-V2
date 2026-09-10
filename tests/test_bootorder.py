import subprocess

from devil.recovery.executor import RecoveryExecutor, RepairReport


def completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_promote_boot_order_puts_devil_first():
    calls = []

    def command(argv, cwd):
        calls.append(tuple(argv))
        if argv[:2] == ("efibootmgr", "--verbose"):
            return completed(
                "BootCurrent: 0000\n"
                "BootOrder: 0000,0001,0002\n"
                "Boot0000* Windows Boot Manager\n"
                "Boot0001* DEVIL-GRUB\n"
                "Boot0002* ubuntu\n"
            )
        if argv[:2] == ("efibootmgr", "-o"):
            return completed()
        raise AssertionError(argv)

    executor = RecoveryExecutor(command=command)
    report = RepairReport(started_at="now")
    executor._promote_boot_order(report)

    assert calls[-1] == ("efibootmgr", "-o", "0001,0000,0002")
    assert report.steps[-1]["status"] == "ok"


def test_promote_boot_order_does_not_write_when_already_first():
    calls = []

    def command(argv, cwd):
        calls.append(tuple(argv))
        if argv[:2] == ("efibootmgr", "--verbose"):
            return completed(
                "BootCurrent: 0001\n"
                "BootOrder: 0001,0000\n"
                "Boot0000* Windows Boot Manager\n"
                "Boot0001* DEVIL-GRUB\n"
            )
        raise AssertionError(argv)

    executor = RecoveryExecutor(command=command)
    report = RepairReport(started_at="now")
    executor._promote_boot_order(report)

    assert calls == [("efibootmgr", "--verbose")]
    assert "already first" in report.steps[-1]["detail"]
