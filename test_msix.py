"""Microsoft Store MSIX 身分與 manifest 測試。"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import build_msix

EXPECTED_NAME = "eric.chuang.SnipTag"
EXPECTED_PUBLISHER = "CN=D21DCC34-9429-4C62-9F60-7E9C7A9F056B"
EXPECTED_DISPLAY_NAME = "eric.chuang"

NS = {
    "f": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "desktop": "http://schemas.microsoft.com/appx/manifest/desktop/windows10",
    "rescap": (
        "http://schemas.microsoft.com/appx/manifest/"
        "foundation/windows10/restrictedcapabilities"
    ),
}


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def main() -> None:
    version = build_msix.store_version()
    manifest = build_msix.MANIFEST_TEMPLATE.read_text(encoding="utf-8").format(
        version=version
    )
    root = ET.fromstring(manifest)

    print("Partner Center 身分")
    identity = root.find("f:Identity", NS)
    check(identity is not None, "有 Identity")
    check(identity.get("Name") == EXPECTED_NAME, "Package Name 正確")
    check(identity.get("Publisher") == EXPECTED_PUBLISHER, "Publisher 正確")
    check(identity.get("Version") == "1.2.2.0", "四段式 Store 版本正確且以 0 結尾")
    publisher_name = root.findtext("f:Properties/f:PublisherDisplayName", namespaces=NS)
    check(publisher_name == EXPECTED_DISPLAY_NAME, "Publisher Display Name 正確")
    resources = root.findall("f:Resources/f:Resource", NS)
    check([resource.get("Language") for resource in resources] == ["zh-tw"],
          "只宣告程式實際支援的繁體中文")

    print("桌面應用程式宣告")
    app = root.find("f:Applications/f:Application", NS)
    check(app is not None and app.get("Executable") == "SnipTag.exe", "入口是 SnipTag.exe")
    startup = root.find(
        "f:Applications/f:Application/f:Extensions/desktop:Extension/desktop:StartupTask",
        NS,
    )
    check(startup is not None, "有 MSIX 開機啟動工作")
    check(startup.get("Enabled") == "true", "開機啟動預設啟用")
    capability = root.find("f:Capabilities/rescap:Capability", NS)
    check(capability is not None and capability.get("Name") == "runFullTrust",
          "桌面截圖與全域熱鍵所需的 runFullTrust 已宣告")

    print("\n全部通過。")


if __name__ == "__main__":
    main()
