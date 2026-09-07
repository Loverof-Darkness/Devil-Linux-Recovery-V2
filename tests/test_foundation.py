import tempfile
import unittest
from pathlib import Path

from devil.detection import detect_firmware_mode
from devil.models.system import OperatingSystem


class FoundationTests(unittest.TestCase):
    def test_unknown_firmware_without_efi_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(detect_firmware_mode(tmp), "BIOS/UNKNOWN")

    def test_uefi_is_detected_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            efi = Path(tmp) / "firmware" / "efi"
            efi.mkdir(parents=True)
            self.assertEqual(detect_firmware_mode(tmp), "UEFI")

    def test_operating_system_model(self) -> None:
        os_record = OperatingSystem(name="Garuda Linux", family="Linux", confidence=1.0)
        self.assertTrue(os_record.is_linux())


if __name__ == "__main__":
    unittest.main()
