"""滾動截圖：把連續的畫面接成一張長圖。

沒有任何 API 會告訴我們「剛才捲了幾個像素」—— 捲動量取決於系統設定、
應用程式自己的實作、有沒有平滑捲動動畫。唯一可靠的依據是畫面本身，
所以這裡用「找重疊」的方式：拿前一張最底下那條當樣板，在新畫面裡找它，
找到之後底下多出來的就是新內容。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtGui import QImage, QPainter

STRIP = 90              # 當樣板的那一條有多高（實體像素）
COLUMNS = 96            # 比對時取樣幾個直行
MIN_ADVANCE = 4         # 少於這麼多像素就當作沒有捲動

# 螢幕截圖的真實重疊是「同一批像素」，平均差應該趨近 0；
# 分數低於這個值就直接信（游標閃爍、少量動畫造成的微小差異涵蓋在內）。
EXACT_THRESHOLD = 0.5
# 沒那麼精確時的絕對上限：完全無重疊的假匹配實測最好也只到 7 左右。
MATCH_THRESHOLD = 4.0
# 文件裡一行行的文字，行距的整數倍會「看起來也很像」（實測這種假匹配
# 約 0.9～1.9 分）。不夠精確的匹配必須是個尖銳低點：明顯優於鄰域外的
# 次佳解才收。寧可判定失敗請使用者重捲，也不要接出錯位的長圖。
RUNNER_UP_RATIO = 0.25


@dataclass
class Match:
    """一次比對的結果。"""

    advance: int        # 這一張比前一張多出多少新內容（實體像素）
    score: float        # 平均像素差，越小越吻合
    position: int       # 樣板在新畫面中的位置
    runner_up: float = float("inf")   # 鄰域以外最好的分數

    @property
    def confident(self) -> bool:
        if self.score <= EXACT_THRESHOLD:
            return True                 # 像素幾乎全等，就是它
        if self.score > MATCH_THRESHOLD:
            return False
        if self.runner_up == float("inf"):
            return True                 # 只有一個候選位置
        return self.score <= self.runner_up * RUNNER_UP_RATIO


def to_signature(image: QImage) -> np.ndarray:
    """把畫面壓成 (高, COLUMNS) 的灰階陣列，比對時只看這些取樣點。"""
    grayscale = image.convertToFormat(QImage.Format_Grayscale8)
    height, width = grayscale.height(), grayscale.width()
    if height == 0 or width == 0:
        return np.zeros((0, COLUMNS), dtype=np.int16)

    buffer = np.frombuffer(memoryview(grayscale.constBits()), dtype=np.uint8)
    # 每一列在記憶體裡會補齊到 4 的倍數，要用 bytesPerLine 而不是寬度
    rows = buffer[:height * grayscale.bytesPerLine()].reshape(
        height, grayscale.bytesPerLine())[:, :width]
    columns = np.linspace(0, width - 1, min(COLUMNS, width)).astype(np.int32)
    return rows[:, columns].astype(np.int16)


def find_overlap(previous: np.ndarray, current: np.ndarray,
                 strip: int = STRIP) -> Match:
    """在 current 裡找出 previous 底部那一條的位置。"""
    height = previous.shape[0]
    strip = min(strip, height, current.shape[0])
    if strip < 4:
        return Match(0, float("inf"), 0)

    template = previous[height - strip:]
    limit = current.shape[0] - strip
    if limit <= 0:
        return Match(0, float("inf"), 0)

    # 逐列滑動比對。只比一條而不是整張，速度差很多。
    scores = np.empty(limit + 1, dtype=np.float32)
    for offset in range(limit + 1):
        window = current[offset:offset + strip]
        scores[offset] = np.abs(window - template).mean()

    position = int(np.argmin(scores))
    advance = (height - strip) - position

    # 把最佳解附近遮掉，看看「別的地方」最好能到多少
    neighbourhood = np.ones(scores.shape, dtype=bool)
    spread = max(4, strip // 2)
    neighbourhood[max(0, position - spread):position + spread + 1] = False
    runner_up = (float(scores[neighbourhood].min())
                 if neighbourhood.any() else float("inf"))

    return Match(advance, float(scores[position]), position, runner_up)


class Stitcher:
    """一張一張餵進來，逐步接成長圖。"""

    def __init__(self) -> None:
        self.frames: list[QImage] = []
        self._signature: np.ndarray | None = None
        self._canvas: QImage | None = None
        self.total_advance = 0
        self.rejected = 0

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def height(self) -> int:
        return self._canvas.height() if self._canvas else 0

    def add(self, frame: QImage) -> int:
        """回傳這一張貢獻了幾像素的新內容；0 表示沒有新東西。"""
        signature = to_signature(frame)
        if self._canvas is None:
            self.frames.append(frame)
            self._canvas = QImage(frame)
            self._signature = signature
            return frame.height()

        if signature.shape != self._signature.shape:
            self.rejected += 1
            return 0                    # 尺寸變了（換視窗？），忽略

        match = find_overlap(self._signature, signature)
        if not match.confident:
            self.rejected += 1
            return 0
        if match.advance < MIN_ADVANCE:
            return 0                    # 還在原地

        new_rows = match.position + STRIP
        added = frame.height() - new_rows
        if added <= 0:
            return 0

        self._canvas = _append(self._canvas, frame, new_rows)
        self._signature = signature
        self.frames.append(frame)
        self.total_advance += match.advance
        return added

    def result(self) -> QImage | None:
        return self._canvas


def _append(canvas: QImage, frame: QImage, from_row: int) -> QImage:
    """把 frame 從 from_row 開始的部分接到 canvas 底下。"""
    extra = frame.height() - from_row
    combined = QImage(canvas.width(), canvas.height() + extra, canvas.format())
    combined.setDevicePixelRatio(canvas.devicePixelRatio())

    painter = QPainter(combined)
    painter.drawImage(0, 0, canvas)
    painter.drawImage(0, canvas.height(), frame, 0, from_row,
                      frame.width(), extra)
    painter.end()
    return combined
