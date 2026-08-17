"""滾動截圖介面流程測試：python test_scrollsession.py

不開計時器、不抓真實螢幕：直接餵合成畫面、手動呼叫 _tick()，
驗證的是「畫面進來之後，狀態、警告、收尾有沒有做對」。
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from sniptag import scrollsession
from sniptag.scrollsession import ScrollSession
from test_scroll import ARTICLE, VIEW, WIDTH, build_article, frame_at


class FakeApp:
    def __init__(self) -> None:
        self.saved = []
        self.notices = []
        self.forgotten = 0

    def finish_scroll(self, pixmap) -> None:
        self.saved.append(pixmap)

    def notify(self, title, message, *args) -> None:
        self.notices.append(f"{title}:{message}")

    def forget_scroll_session(self, session) -> None:
        self.forgotten += 1


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def new_session(app: FakeApp, frames) -> ScrollSession:
    iterator = iter(frames)
    session = ScrollSession(app, QRect(50, 50, WIDTH, VIEW),
                            frame_source=lambda: next(iterator, None))
    session.dpr = 1.0
    return session


def main() -> None:
    qapp = QApplication.instance() or QApplication(sys.argv)
    article = build_article()

    print("正常流程")
    app = FakeApp()
    offsets = list(range(0, 601, 75))
    session = new_session(app, [frame_at(article, o) for o in offsets])
    for _ in offsets:
        session._tick()
    check(len(session.stitcher) == len(offsets), "每張都接上了")
    check("段" in session.stats_label.text(), "狀態列有更新")
    check(session.warn_label.isHidden(), "沒有警告")
    session.finish()
    check(len(app.saved) == 1, "完成時把長圖交回給 app")
    result = app.saved[0]
    check(result.height() == offsets[-1] + VIEW,
          f"長圖高度正確（{result.height()}）")
    check(app.forgotten == 1, "app 端的參考已解除")
    session_finish_again_is_safe = True
    try:
        session.finish()
    except Exception:
        session_finish_again_is_safe = False
    check(session_finish_again_is_safe and len(app.saved) == 1,
          "重複 finish 不會存兩份")

    print("接不上時的警告")
    app = FakeApp()
    session = new_session(app, [
        frame_at(article, 0),
        frame_at(article, 1200),     # 跳太遠，接不上
        frame_at(article, 80),       # 回來慢慢捲，接得上
    ])
    session._tick()
    check(session.warn_label.isHidden(), "第一張沒有警告")
    session._tick()
    check(not session.warn_label.isHidden(), "接不上 -> 顯示警告")
    session._tick()
    check(session.warn_label.isHidden(), "下一段成功 -> 警告收掉")
    session.cancel()
    check(len(app.saved) == 0, "取消不會存檔")
    check(app.forgotten == 1, "取消也會解除參考")

    print("空的 session")
    app = FakeApp()
    session = new_session(app, [])
    session._tick()      # 來源回 None
    session.finish()
    check(len(app.saved) == 0, "沒有內容就不存")
    check(any("沒有擷取到" in n for n in app.notices), "但會告訴使用者")

    print("超過長度上限自動完成")
    app = FakeApp()
    limit = scrollsession.MAX_HEIGHT
    scrollsession.MAX_HEIGHT = 900
    try:
        session = new_session(app, [frame_at(article, o)
                                    for o in range(0, ARTICLE - VIEW, 100)])
        for _ in range(20):
            if session._finished:
                break
            session._tick()
        check(session._finished, "到達上限自動收尾")
        check(len(app.saved) == 1 and app.saved[0].height() >= 900,
              "產出的長圖已達上限高度")
    finally:
        scrollsession.MAX_HEIGHT = limit

    print("\n全部通過。")
    del qapp


if __name__ == "__main__":
    main()
