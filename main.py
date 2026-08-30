# Added features



# Preview LED Layout button in the Image / Curves tab.

# LED count + coverage stats



# Shows total LED count.

# Shows weighted coverage percentage.

# Shows per-segment LED count, coverage, and density.





# Color-coded illumination density



# Blue: under-covered / low coverage area.

# Green: normal density.

# Orange: moderate overlap.

# Red: high overlap / dense LED areas.





# Visual LED overlay



# Draws illumination circles from the LED centers.

# Draws LED body markers.

# Labels each segment with LED count and coverage.





# No KiCad / STL / PDF export behavior changed



# The preview uses the same placement calculations, but it does not alter export workflows.

















import sys, os, re, math, json, uuid, traceback, tempfile

from pathlib import Path

import numpy as np



from PySide6.QtCore import Qt, QPointF, QLineF, QUrl

from PySide6.QtGui import QAction, QPixmap, QPen, QColor, QBrush, QPainter, QFont, QPainterPath, QDesktopServices

from PySide6.QtWidgets import (

    QApplication, QMainWindow, QFileDialog, QGraphicsView, QGraphicsScene,

    QGraphicsPixmapItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsTextItem,

    QGraphicsItem, QGraphicsLineItem, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,

    QPushButton, QLabel, QDoubleSpinBox, QSpinBox, QListWidget, QMessageBox,

    QComboBox, QTabWidget, QGroupBox, QDialog, QLineEdit, QColorDialog,

    QDialogButtonBox,

)

try:

    from PySide6.QtPdf import QPdfDocument

    from PySide6.QtPdfWidgets import QPdfView

except Exception:

    QPdfDocument = None

    QPdfView = None



from geometry import create_extruded_stl, create_extruded_mesh



KICAD_FILE_VERSION = 20250114

NORMAL_CURVE_WIDTH = 1.0

TYPE_CURVE_WIDTH = 1.5

SELECTED_CURVE_WIDTH = 2.5

PREVIEW_LINE_WIDTH = 1.0

HANDLE_GUIDE_LINE_WIDTH = 0.5

MANUAL_POINT_RADIUS = 2

ANCHOR_POINT_RADIUS = 3

HANDLE_POINT_RADIUS = 2

UNSELECTED_LABEL_COLOR = QColor(160, 32, 240)

SELECTED_LABEL_COLOR = QColor("darkorange")

DEFAULT_BORDER_COLOR = "#000000"

DEFAULT_HOLE_COLOR = "#ffffff"

DEFAULT_CURVE_COLOR = "#00ff00"

PDF_PAGE_TYPES = ["Actual Size", "A4 Portrait", "A4 Landscape", "A5 Portrait", "A5 Landscape"]

LED_FOOTPRINTS = [

    "LED_SMD:LED_01005_0402Metric",

    "LED_SMD:LED_0201_0603Metric",

    "LED_SMD:LED_0402_1005Metric",

    "LED_SMD:LED_0603_1608Metric",

    "LED_SMD:LED_0805_2012Metric",

    "LED_SMD:LED_1206_3216Metric",

]

LED_BODY_SIZE_MM = {

    "LED_SMD:LED_01005_0402Metric": (0.40, 0.20),

    "LED_SMD:LED_0201_0603Metric": (0.60, 0.30),

    "LED_SMD:LED_0402_1005Metric": (1.00, 0.50),

    "LED_SMD:LED_0603_1608Metric": (1.60, 0.80),

    "LED_SMD:LED_0805_2012Metric": (2.00, 1.25),

    "LED_SMD:LED_1206_3216Metric": (3.20, 1.60),

}

LED_PAD_FALLBACK = {

    "LED_SMD:LED_01005_0402Metric": (0.20, 0.16, 0.16),

    "LED_SMD:LED_0201_0603Metric": (0.28, 0.25, 0.28),

    "LED_SMD:LED_0402_1005Metric": (0.45, 0.50, 0.48),

    "LED_SMD:LED_0603_1608Metric": (0.70, 0.80, 0.75),

    "LED_SMD:LED_0805_2012Metric": (0.95, 1.05, 0.95),

    "LED_SMD:LED_1206_3216Metric": (1.15, 1.40, 1.45),

}





def qpoint_to_list(p):

    return [float(p.x()), float(p.y())]





def list_to_qpoint(v):

    return QPointF(float(v[0]), float(v[1]))





def color_with_alpha(hex_color, alpha=96):

    c = QColor(hex_color or DEFAULT_CURVE_COLOR)

    c.setAlpha(alpha)

    return c





def norm_angle(a):

    return float(a) % 360.0





class CurveStyleDialog(QDialog):

    def __init__(self, parent, title, current_color, current_name=None, show_name=False):

        super().__init__(parent)

        self.setWindowTitle(title)

        self.selected_color = QColor(current_color or DEFAULT_HOLE_COLOR)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Color"))

        self.preview = QLabel()

        self.preview.setMinimumHeight(34)

        self.preview.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.preview)

        grid = QGridLayout()

        colors = ["#000000", "#ffffff", "#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff", "#808080", "#ffa500", "#800080", "#8b4513", "#ffc0cb", "#add8e6", "#90ee90"]

        for i, hx in enumerate(colors):

            b = QPushButton()

            b.setFixedSize(30, 24)

            b.setStyleSheet(f"background-color:{hx}; border:1px solid #555;")

            b.clicked.connect(lambda checked=False, c=hx: self.set_color(QColor(c)))

            grid.addWidget(b, i // 5, i % 5)

        layout.addLayout(grid)

        custom = QPushButton("Custom color...")

        custom.clicked.connect(self.choose_custom_color)

        layout.addWidget(custom)

        self.name_edit = None

        if show_name:

            layout.addWidget(QLabel("Segment name"))

            self.name_edit = QLineEdit(current_name or "")

            layout.addWidget(self.name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        buttons.accepted.connect(self.accept)

        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        self.update_preview()



    def set_color(self, c):

        if c.isValid():

            c.setAlpha(255)

            self.selected_color = c

            self.update_preview()



    def choose_custom_color(self):

        c = QColorDialog.getColor(self.selected_color, self, "Choose custom color")

        if c.isValid():

            self.set_color(c)



    def update_preview(self):

        self.preview.setStyleSheet(f"background-color:{self.selected_color.name()}; border:1px solid #555;")

        self.preview.setText(self.selected_color.name())



    def color_hex(self):

        return self.selected_color.name()



    def segment_name(self):

        return (self.name_edit.text().strip() or None) if self.name_edit else None





class BezierEditPoint(QGraphicsEllipseItem):

    def __init__(self, canvas, loop_index, point_index, kind, position, radius, color):

        super().__init__(-radius, -radius, radius * 2, radius * 2)

        self.canvas = canvas

        self.loop_index = loop_index

        self.point_index = point_index

        self.kind = kind

        self.suppress_change = False

        self.setPos(position)

        self.setBrush(QBrush(color))

        pen = QPen(QColor("black"))

        pen.setWidthF(0.5)

        self.setPen(pen)

        self.setZValue(200)

        self.setFlag(QGraphicsItem.ItemIsMovable, True)

        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        self.setCursor(Qt.OpenHandCursor)



    def mousePressEvent(self, event):

        self.setCursor(Qt.ClosedHandCursor)

        if self.canvas.selected_loop_index != self.loop_index:

            self.canvas.select_loop(self.loop_index)

        if self.kind == "anchor":

            self.canvas.selected_anchor_index = self.point_index

            if self.canvas.edit_mode == "delete_point":

                self.canvas.delete_anchor_point(self.loop_index, self.point_index)

                event.accept()

                return

        super().mousePressEvent(event)



    def mouseReleaseEvent(self, event):

        self.setCursor(Qt.OpenHandCursor)

        self.canvas.push_undo_state_after_drag_if_needed()

        super().mouseReleaseEvent(event)



    def itemChange(self, change, value):

        if change == QGraphicsItem.ItemPositionHasChanged and not self.suppress_change:

            self.canvas.on_bezier_edit_point_moved(self.loop_index, self.point_index, self.kind, QPointF(value))

        return super().itemChange(change, value)





class ImageCanvas(QGraphicsView):

    def __init__(self):

        super().__init__()

        self.scene = QGraphicsScene()

        self.setScene(self.scene)

        self.image_item = None

        self.current_image_path = None

        self.current_points = []

        self.current_point_items = []

        self.current_preview_item = None

        self.loops = []

        self.selected_loop_index = None

        self.selected_anchor_index = None

        self.edit_items = []

        self.edit_lines = []

        self.error_items = []

        self.led_preview_items = []

        self.undo_stack = []

        self.drag_undo_state = None

        self.edit_mode = "select"

        self.grid_visible = True

        self.unit_name = "millimeter"

        self.units_per_pixel = 1.0

        self.label_font_factor = 0.15

        self.label_min_font_size = 8

        self.label_max_font_size = 72

        self.is_panning = False

        self.space_key_down = False

        self.last_pan_position = None

        self.cursor_position_callback = None

        self.loops_changed_callback = None

        self.loop_selected_callback = None

        self.mode_changed_callback = None

        self.setRenderHint(QPainter.Antialiasing)

        self.setMouseTracking(True)

        self.setFocusPolicy(Qt.StrongFocus)

        self.setInteractive(True)

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)



    def serialize_loop(self, l):

        return {"name": l.get("name", ""), "custom_name": l.get("custom_name"), "type": l.get("type", "unassigned"), "fill_color": l.get("fill_color", DEFAULT_CURVE_COLOR), "smooth_handles": bool(l.get("smooth_handles", True)), "anchors": [qpoint_to_list(p) for p in l.get("anchors", [])], "handles_in": [qpoint_to_list(p) for p in l.get("handles_in", [])], "handles_out": [qpoint_to_list(p) for p in l.get("handles_out", [])]}



    def serialize_state(self):

        return {"loops": [self.serialize_loop(l) for l in self.loops], "current_points": [qpoint_to_list(p) for p in self.current_points], "selected_loop_index": self.selected_loop_index}



    def push_undo_state(self):

        self.undo_stack.append(self.serialize_state())

        self.undo_stack = self.undo_stack[-50:]



    def begin_drag_undo_state(self):

        if self.drag_undo_state is None:

            self.drag_undo_state = self.serialize_state()



    def push_undo_state_after_drag_if_needed(self):

        if self.drag_undo_state is not None:

            self.undo_stack.append(self.drag_undo_state)

            self.undo_stack = self.undo_stack[-50:]

            self.drag_undo_state = None

            self.notify_loops_changed()



    def undo(self):

        if self.undo_stack:

            self.restore_state(self.undo_stack.pop())



    def clear_error_arrows(self):

        for item in self.error_items:

            try:

                self.scene.removeItem(item)

            except Exception:

                pass

        self.error_items = []





    def clear_led_preview(self):

        for item in self.led_preview_items:

            try:

                self.scene.removeItem(item)

            except Exception:

                pass

        self.led_preview_items = []



    def add_led_preview_circle(self, center_px, radius_px, color, tooltip=""):

        item = QGraphicsEllipseItem(center_px[0] - radius_px, center_px[1] - radius_px, radius_px * 2, radius_px * 2)

        item.setBrush(QBrush(color))

        pen = QPen(QColor(color.red(), color.green(), color.blue(), min(255, color.alpha() + 80)))

        pen.setWidthF(0.8)

        item.setPen(pen)

        item.setZValue(120)

        if tooltip:

            item.setToolTip(tooltip)

        self.scene.addItem(item)

        self.led_preview_items.append(item)

        return item



    def add_led_preview_body(self, center_px, body_w_px, body_h_px, angle_deg, color, tooltip=""):

        # Body rectangle approximated with an ellipse/box footprint marker in the image editor only.

        item = QGraphicsEllipseItem(center_px[0] - body_w_px/2, center_px[1] - body_h_px/2, body_w_px, body_h_px)

        item.setBrush(QBrush(color))

        pen = QPen(QColor("black")); pen.setWidthF(0.4); item.setPen(pen)

        item.setRotation(angle_deg)

        item.setTransformOriginPoint(center_px[0], center_px[1])

        item.setZValue(130)

        if tooltip:

            item.setToolTip(tooltip)

        self.scene.addItem(item)

        self.led_preview_items.append(item)

        return item



    def add_led_preview_text(self, text, pos_px):

        item = QGraphicsTextItem(text)

        item.setDefaultTextColor(QColor("white"))

        item.setFont(QFont("Arial", 10, QFont.Bold))

        item.setPos(pos_px[0], pos_px[1])

        item.setZValue(140)

        self.scene.addItem(item)

        self.led_preview_items.append(item)

        return item



    def show_error_arrow_for_loop(self, loop_index, text="LED does not fit"):

        self.clear_error_arrows()

        if not (0 <= loop_index < len(self.loops)):

            return

        rect = self.loops[loop_index]["item"].path().boundingRect()

        c = rect.center()

        start = QPointF(rect.left() - max(25, rect.width() * 0.35), rect.top() - max(25, rect.height() * 0.35))

        end = QPointF(c.x(), c.y())

        pen = QPen(QColor("red")); pen.setWidthF(3)

        line = QGraphicsLineItem(QLineF(start, end)); line.setPen(pen); line.setZValue(500); self.scene.addItem(line); self.error_items.append(line)

        angle = math.atan2(end.y()-start.y(), end.x()-start.x()); size = 12

        p1 = QPointF(end.x() - size*math.cos(angle-math.pi/6), end.y() - size*math.sin(angle-math.pi/6))

        p2 = QPointF(end.x() - size*math.cos(angle+math.pi/6), end.y() - size*math.sin(angle+math.pi/6))

        for a, b in [(end, p1), (end, p2)]:

            l = QGraphicsLineItem(QLineF(a, b)); l.setPen(pen); l.setZValue(501); self.scene.addItem(l); self.error_items.append(l)

        label = QGraphicsTextItem(text); label.setDefaultTextColor(QColor("red")); label.setFont(QFont("Arial", 12, QFont.Bold)); label.setPos(start); label.setZValue(502); self.scene.addItem(label); self.error_items.append(label)



    def clear_all_except_image(self, push_undo=True):

        if push_undo:

            self.push_undo_state()

        self.clear_edit_items(); self.clear_error_arrows(); self.clear_led_preview()

        for d in self.current_point_items:

            self.scene.removeItem(d)

        if self.current_preview_item is not None:

            self.scene.removeItem(self.current_preview_item); self.current_preview_item = None

        for l in self.loops:

            self.scene.removeItem(l["item"]); self.scene.removeItem(l["label_item"])

        self.current_points = []; self.current_point_items = []; self.loops = []; self.selected_loop_index = None; self.selected_anchor_index = None; self.notify_loops_changed()

        if self.loop_selected_callback: self.loop_selected_callback(None)



    def restore_state(self, state):

        self.clear_all_except_image(push_undo=False)

        for p in state.get("current_points", []): self.add_current_point(list_to_qpoint(p), push_undo=False)

        for ld in state.get("loops", []): self.create_loop_from_serialized(ld)

        sel = state.get("selected_loop_index"); self.select_loop(sel if sel is not None and 0 <= sel < len(self.loops) else None); self.notify_loops_changed()



    def load_image(self, fp):

        self.scene.clear(); self.image_item = None; self.current_image_path = fp; self.current_points = []; self.current_point_items = []; self.current_preview_item = None; self.loops = []; self.selected_loop_index = None; self.selected_anchor_index = None; self.edit_items = []; self.edit_lines = []; self.error_items = []; self.led_preview_items = []; self.undo_stack = []

        pix = QPixmap(fp)

        if pix.isNull(): raise ValueError("Could not load image.")

        self.image_item = QGraphicsPixmapItem(pix); self.image_item.setZValue(0); self.scene.addItem(self.image_item); self.setSceneRect(self.image_item.boundingRect()); self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio); self.notify_loops_changed()



    def set_edit_mode(self, mode):

        self.edit_mode = mode; self.setCursor(Qt.ArrowCursor if mode == "select" else Qt.CrossCursor if mode == "add_point" else Qt.PointingHandCursor)

        if self.mode_changed_callback: self.mode_changed_callback(mode)



    def set_grid_settings(self, unit_name, units_per_pixel): self.unit_name = unit_name; self.units_per_pixel = units_per_pixel; self.viewport().update()

    def set_label_font_factor(self, f): self.label_font_factor = f; [self.update_loop_label(i) for i in range(len(self.loops))]

    def nice_number(self, v):

        if v <= 0: return 1

        e = math.floor(math.log10(v)); f = v / (10 ** e); nf = 1 if f <= 1 else 2 if f <= 2 else 5 if f <= 5 else 10; return nf * (10 ** e)



    def drawBackground(self, painter, rect):

        super().drawBackground(painter, rect)

        if not self.grid_visible or self.units_per_pixel <= 0: return

        zoom = self.transform().m11() or 1; minor = self.nice_number((40 / zoom) * self.units_per_pixel) / self.units_per_pixel

        if minor <= 0: return

        major = minor * 5; left = math.floor(rect.left() / minor) * minor; right = rect.right(); top = math.floor(rect.top() / minor) * minor; bottom = rect.bottom()

        minor_pen = QPen(QColor(210, 210, 210, 120)); minor_pen.setWidthF(0); major_pen = QPen(QColor(120, 120, 120, 180)); major_pen.setWidthF(0); axis_pen = QPen(QColor(80, 80, 255, 220)); axis_pen.setWidthF(0)

        x = left

        while x <= right:

            painter.setPen(axis_pen if abs(x) < 1e-4 else major_pen if abs((x / major) - round(x / major)) < 1e-4 else minor_pen); painter.drawLine(QPointF(x, top), QPointF(x, bottom)); x += minor

        y = top

        while y <= bottom:

            painter.setPen(axis_pen if abs(y) < 1e-4 else major_pen if abs((y / major) - round(y / major)) < 1e-4 else minor_pen); painter.drawLine(QPointF(left, y), QPointF(right, y)); y += minor

        painter.setFont(QFont("Arial", max(7, int(9 / max(zoom, 0.2))))); painter.setPen(QPen(QColor(255, 255, 255, 230)))

        unit_short = "mm" if self.unit_name == "millimeter" else "in"; x = math.floor(rect.left() / major) * major; top_label_y = rect.top() + 14 / zoom

        while x <= right:

            painter.drawText(QPointF(x + 4/zoom, top_label_y), f"X {x*self.units_per_pixel:.3g} {unit_short}"); x += major

        y = math.floor(rect.top() / major) * major; left_label_x = rect.left() + 4 / zoom

        while y <= bottom:

            painter.drawText(QPointF(left_label_x, y - 4/zoom), f"Y {y*self.units_per_pixel:.3g} {unit_short}"); y += major



    def detect_contours_from_image(self, threshold_value=128, threshold_mode="Dark shapes/lines", min_area=100.0, simplify_pixels=2.0):

        try: import cv2

        except Exception as e: QMessageBox.critical(self, "OpenCV import error", str(e)); return

        if not self.current_image_path: QMessageBox.warning(self, "No image", "Please open an image first."); return

        self.push_undo_state(); img = cv2.imread(self.current_image_path)

        if img is None: QMessageBox.warning(self, "Image error", "OpenCV could not read the image."); return

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); typ = cv2.THRESH_BINARY_INV if threshold_mode == "Dark shapes/lines" else cv2.THRESH_BINARY; _, binary = cv2.threshold(gray, threshold_value, 255, typ); contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

        cand = []

        for contour in contours:

            area = abs(cv2.contourArea(contour))

            if area < min_area or len(contour) < 3: continue

            per = cv2.arcLength(contour, True)

            if per <= 0: continue

            anchors = self.approximate_contour_with_few_points(contour, per, simplify_pixels)

            if len(anchors) >= 3: cand.append({"anchors": anchors, "area": area, "smooth_handles": self.contour_should_be_smooth(anchors)})

        cand.sort(key=lambda c: c["area"], reverse=True)

        if not cand: QMessageBox.information(self, "No contours found", "No contours were detected."); return

        first = len(self.loops)

        for c in cand: self.create_loop_from_anchors(c["anchors"], False, c["smooth_handles"], False)

        self.update_loop_names_and_labels(); self.select_loop(first); self.notify_loops_changed()



    def approximate_contour_with_few_points(self, contour, per, simp):

        import cv2

        eps = max(float(simp), per * 0.01); best = []

        while eps <= per * 0.12:

            approx = cv2.approxPolyDP(contour, eps, True); anchors = [QPointF(float(p[0][0]), float(p[0][1])) for p in approx]

            if len(anchors) >= 3: best = anchors

            if 3 <= len(anchors) <= 10: break

            eps *= 1.35

        return best

    def angle_between_points(self, a, b, c):

        v1 = (a.x()-b.x(), a.y()-b.y()); v2 = (c.x()-b.x(), c.y()-b.y()); l1 = math.hypot(*v1); l2 = math.hypot(*v2)

        if l1 <= 0 or l2 <= 0: return 180.0

        return math.degrees(math.acos(max(-1, min(1, (v1[0]*v2[0]+v1[1]*v2[1])/(l1*l2)))))

    def contour_should_be_smooth(self, anchors):

        n = len(anchors)

        if n <= 6: return False

        if n >= 14: return True

        sharp = sum(1 for i in range(n) if self.angle_between_points(anchors[(i-1)%n], anchors[i], anchors[(i+1)%n]) < 135); return sharp / n < 0.35

    def auto_handles_from_anchors(self, anchors):

        n = len(anchors); hi = []; ho = []

        for i in range(n):

            p = anchors[(i-1)%n]; c = anchors[i]; nx = anchors[(i+1)%n]; t = QPointF(nx.x()-p.x(), nx.y()-p.y()); ho.append(QPointF(c.x()+t.x()/6, c.y()+t.y()/6)); hi.append(QPointF(c.x()-t.x()/6, c.y()-t.y()/6))

        return hi, ho

    def straight_handles_from_anchors(self, anchors):

        n = len(anchors); hi = []; ho = []

        for i in range(n):

            p = anchors[(i-1)%n]; c = anchors[i]; nx = anchors[(i+1)%n]; hi.append(QPointF(c.x()+(p.x()-c.x())/3, c.y()+(p.y()-c.y())/3)); ho.append(QPointF(c.x()+(nx.x()-c.x())/3, c.y()+(nx.y()-c.y())/3))

        return hi, ho

    def build_bezier_path(self, anchors, hi, ho):

        path = QPainterPath()

        if not anchors: return path

        path.moveTo(anchors[0]); n = len(anchors)

        for i in range(n): path.cubicTo(ho[i], hi[(i+1)%n], anchors[(i+1)%n])

        path.closeSubpath(); return path

    def sample_cubic_bezier(self, p0, c1, c2, p3, steps=24):

        pts = []

        for s in range(steps):

            t = s / steps; x = ((1-t)**3)*p0.x()+3*((1-t)**2)*t*c1.x()+3*(1-t)*(t**2)*c2.x()+(t**3)*p3.x(); y = ((1-t)**3)*p0.y()+3*((1-t)**2)*t*c1.y()+3*(1-t)*(t**2)*c2.y()+(t**3)*p3.y(); pts.append((x,y))

        return pts

    def sample_loop(self, anchors, hi, ho, steps_per_segment=24):

        pts = []

        for i in range(len(anchors)): pts += self.sample_cubic_bezier(anchors[i], ho[i], hi[(i+1)%len(anchors)], anchors[(i+1)%len(anchors)], steps_per_segment)

        return pts

    def wheelEvent(self, e):

        if self.image_item is not None:

            f = 1.25 if e.angleDelta().y() > 0 else 1/1.25; self.scale(f, f)

    def begin_pan(self, event): self.is_panning = True; self.last_pan_position = event.position(); self.setCursor(Qt.ClosedHandCursor)

    def mousePressEvent(self, e):

        if self.image_item is None: return

        self.setFocus()

        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and self.space_key_down): self.begin_pan(e); return

        if e.button() == Qt.LeftButton:

            clicked = self.itemAt(e.position().toPoint())

            if isinstance(clicked, BezierEditPoint): self.begin_drag_undo_state(); super().mousePressEvent(e); return

            pos = self.mapToScene(e.position().toPoint())

            if self.edit_mode == "add_point": self.insert_anchor_point_at_position(pos); return

            if clicked is not None:

                idx = clicked.data(0)

                if idx is not None: self.select_loop(idx); return

            if self.edit_mode == "select": self.add_current_point(pos)

            return

        if e.button() == Qt.RightButton and self.edit_mode == "select": self.close_current_loop(); return

        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):

        pos = self.mapToScene(e.position().toPoint())

        if self.cursor_position_callback: self.cursor_position_callback(pos.x(), pos.y(), pos.x()*self.units_per_pixel, pos.y()*self.units_per_pixel)

        if self.is_panning and self.last_pan_position is not None:

            d = e.position() - self.last_pan_position; self.last_pan_position = e.position(); self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-int(d.x())); self.verticalScrollBar().setValue(self.verticalScrollBar().value()-int(d.y())); return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):

        if e.button() in (Qt.MiddleButton, Qt.LeftButton) and self.is_panning:

            self.is_panning = False; self.last_pan_position = None; self.setCursor(Qt.ArrowCursor if not self.space_key_down else Qt.OpenHandCursor); return

        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):

        if e.key() == Qt.Key_Space: self.space_key_down = True; self.setCursor(Qt.OpenHandCursor); return

        if e.key() == Qt.Key_Z and e.modifiers() & Qt.ControlModifier: self.undo(); return

        if e.key() == Qt.Key_Delete: self.delete_anchor_point(self.selected_loop_index, self.selected_anchor_index) if self.selected_anchor_index is not None and self.selected_loop_index is not None else self.delete_selected_loop(); return

        if e.key() == Qt.Key_A: self.set_edit_mode("add_point"); return

        if e.key() == Qt.Key_D: self.set_edit_mode("delete_point"); return

        if e.key() == Qt.Key_Escape: self.set_edit_mode("select"); return

        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):

        if e.key() == Qt.Key_Space:

            self.space_key_down = False

            if not self.is_panning: self.setCursor(Qt.ArrowCursor)

            return

        super().keyReleaseEvent(e)

    def add_current_point(self, p, push_undo=False):

        if push_undo: self.push_undo_state()

        self.current_points.append(p); r = MANUAL_POINT_RADIUS; dot = QGraphicsEllipseItem(p.x()-r, p.y()-r, r*2, r*2); dot.setBrush(QBrush(QColor("red"))); dot.setZValue(50); self.scene.addItem(dot); self.current_point_items.append(dot); self.update_current_preview()

    def update_current_preview(self):

        if self.current_preview_item is not None: self.scene.removeItem(self.current_preview_item); self.current_preview_item = None

        if len(self.current_points) < 2: return

        path = QPainterPath(); path.moveTo(self.current_points[0])

        for p in self.current_points[1:]: path.lineTo(p)

        pen = QPen(QColor(255,140,0)); pen.setWidthF(PREVIEW_LINE_WIDTH); pen.setStyle(Qt.DashLine); self.current_preview_item = QGraphicsPathItem(path); self.current_preview_item.setPen(pen); self.current_preview_item.setZValue(40); self.scene.addItem(self.current_preview_item)

    def undo_last_point(self):

        if not self.current_points: return

        self.push_undo_state(); self.current_points.pop(); self.scene.removeItem(self.current_point_items.pop()); self.update_current_preview()

    def close_current_loop(self):

        if len(self.current_points) < 3: QMessageBox.warning(self, "Loop error", "A curve needs at least 3 anchor points."); return

        self.push_undo_state(); anchors = list(self.current_points)

        for d in self.current_point_items: self.scene.removeItem(d)

        self.current_points = []; self.current_point_items = []

        if self.current_preview_item is not None: self.scene.removeItem(self.current_preview_item); self.current_preview_item = None

        self.create_loop_from_anchors(anchors, True, True, False)

    def point_to_segment_distance(self, p, a, b):

        px,py = p.x(), p.y(); ax,ay = a.x(), a.y(); bx,by = b.x(), b.y(); dx = bx-ax; dy = by-ay

        if dx == 0 and dy == 0: return math.hypot(px-ax, py-ay), 0

        t = max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy))); return math.hypot(px-(ax+t*dx), py-(ay+t*dy)), t

    def insert_anchor_point_at_position(self, p):

        if self.selected_loop_index is None: QMessageBox.warning(self, "No curve selected", "Select a curve first."); return

        self.push_undo_state(); loop = self.loops[self.selected_loop_index]; anchors = loop["anchors"]; best = 0; bd = 1e99

        for i in range(len(anchors)):

            d,_ = self.point_to_segment_distance(p, anchors[i], anchors[(i+1)%len(anchors)])

            if d < bd: bd = d; best = i

        loop["anchors"].insert(best+1, p); self.rebuild_handles_for_loop(self.selected_loop_index); self.update_loop_geometry(self.selected_loop_index); self.rebuild_edit_items(self.selected_loop_index); self.selected_anchor_index = best+1; self.notify_loops_changed()

    def delete_anchor_point(self, li, pi):

        if li is None or pi is None or not (0 <= li < len(self.loops)): return

        loop = self.loops[li]

        if len(loop["anchors"]) <= 3: QMessageBox.warning(self, "Cannot delete point", "A closed curve needs at least 3 anchor points."); return

        self.push_undo_state(); loop["anchors"].pop(pi); self.rebuild_handles_for_loop(li); self.update_loop_geometry(li); self.rebuild_edit_items(li); self.selected_anchor_index = None; self.notify_loops_changed()

    def rebuild_handles_for_loop(self, i):

        loop = self.loops[i]; hi, ho = self.auto_handles_from_anchors(loop["anchors"]) if loop.get("smooth_handles", True) else self.straight_handles_from_anchors(loop["anchors"]); loop["handles_in"] = hi; loop["handles_out"] = ho

    def create_loop_from_serialized(self, d):

        anchors = [list_to_qpoint(p) for p in d.get("anchors", [])]; hi = [list_to_qpoint(p) for p in d.get("handles_in", [])]; ho = [list_to_qpoint(p) for p in d.get("handles_out", [])]

        if len(anchors) < 3: return None

        if len(hi) != len(anchors) or len(ho) != len(anchors): hi, ho = self.auto_handles_from_anchors(anchors)

        idx = len(self.loops); item = QGraphicsPathItem(); item.setZValue(20); item.setData(0, idx); self.scene.addItem(item); label = QGraphicsTextItem(d.get("name", f"Curve {idx+1}")); label.setZValue(60); label.setData(0, idx); self.scene.addItem(label)

        self.loops.append({"name": d.get("name", f"Curve {idx+1}"), "custom_name": d.get("custom_name"), "anchors": anchors, "handles_in": hi, "handles_out": ho, "smooth_handles": bool(d.get("smooth_handles", True)), "points": [], "type": d.get("type", "unassigned"), "fill_color": d.get("fill_color", DEFAULT_CURVE_COLOR), "item": item, "label_item": label}); self.update_loop_geometry(idx); self.update_loop_names_and_labels(); return idx

    def create_loop_from_anchors(self, anchors, select_after=True, smooth_handles=True, push_undo=False):

        if len(anchors) < 3: QMessageBox.warning(self, "Curve error", "A curve needs at least 3 anchor points."); return None

        if push_undo: self.push_undo_state()

        hi, ho = self.auto_handles_from_anchors(anchors) if smooth_handles else self.straight_handles_from_anchors(anchors); idx = len(self.loops); item = QGraphicsPathItem(); item.setZValue(20); item.setData(0, idx); self.scene.addItem(item); label = QGraphicsTextItem(f"Curve {idx+1}"); label.setZValue(60); label.setData(0, idx); self.scene.addItem(label)

        self.loops.append({"name": f"Curve {idx+1}", "custom_name": None, "anchors": anchors, "handles_in": hi, "handles_out": ho, "smooth_handles": smooth_handles, "points": [], "type": "unassigned", "fill_color": DEFAULT_CURVE_COLOR, "item": item, "label_item": label}); self.update_loop_names_and_labels(); self.update_loop_geometry(idx); self.select_loop(idx) if select_after else None; self.notify_loops_changed(); return idx

    def update_loop_names_and_labels(self):

        seg = 1

        for idx, l in enumerate(self.loops):

            if l["type"] == "outer": l["name"] = "Border"

            elif l["type"] == "hole": l["name"] = l.get("custom_name") or f"Segment {seg}"; seg += 1

            else: l["name"] = f"Curve {idx+1}"

            l["item"].setData(0, idx); l["label_item"].setData(0, idx); self.update_loop_label(idx)

        self.update_loop_colors()

    def on_bezier_edit_point_moved(self, li, pi, kind, pos):

        if not (0 <= li < len(self.loops)): return

        loop = self.loops[li]

        if not (0 <= pi < len(loop["anchors"])): return

        if kind == "anchor":

            old = loop["anchors"][pi]; d = QPointF(pos.x()-old.x(), pos.y()-old.y()); loop["anchors"][pi] = pos; loop["handles_in"][pi] = QPointF(loop["handles_in"][pi].x()+d.x(), loop["handles_in"][pi].y()+d.y()); loop["handles_out"][pi] = QPointF(loop["handles_out"][pi].x()+d.x(), loop["handles_out"][pi].y()+d.y()); self.selected_anchor_index = pi

        elif kind == "handle_in": loop["handles_in"][pi] = pos

        elif kind == "handle_out": loop["handles_out"][pi] = pos

        self.update_loop_geometry(li); self.sync_edit_items_to_loop(li)

    def update_loop_geometry(self, i):

        if not (0 <= i < len(self.loops)): return

        l = self.loops[i]; l["item"].setPath(self.build_bezier_path(l["anchors"], l["handles_in"], l["handles_out"])); l["points"] = self.sample_loop(l["anchors"], l["handles_in"], l["handles_out"]); self.update_loop_label(i); self.update_loop_colors()

    def update_loop_label(self, i):

        if not (0 <= i < len(self.loops)): return

        l = self.loops[i]; lab = l["label_item"]; lab.setPlainText(l["name"]); rect = l["item"].path().boundingRect(); fs = max(self.label_min_font_size, min(self.label_max_font_size, min(rect.width(), rect.height()) * self.label_font_factor)); font = QFont("Arial"); font.setBold(True); font.setPointSizeF(fs); lab.setFont(font); tr = lab.boundingRect()

        if l["type"] == "outer":

            pad = max(4, fs * 0.25); lab.setPos(rect.right() - tr.width() - pad, rect.bottom() - tr.height() - pad)

        else:

            c = rect.center(); lab.setPos(c.x() - tr.width()/2, c.y() - tr.height()/2)

    def clear_edit_items(self):

        for it in self.edit_items: self.scene.removeItem(it)

        for ln in self.edit_lines: self.scene.removeItem(ln)

        self.edit_items = []; self.edit_lines = []

    def rebuild_edit_items(self, i):

        self.clear_edit_items()

        if not (0 <= i < len(self.loops)): return

        l = self.loops[i]; pen = QPen(QColor(80,80,80,180)); pen.setWidthF(HANDLE_GUIDE_LINE_WIDTH); pen.setStyle(Qt.DashLine)

        for k, a in enumerate(l["anchors"]):

            li = QGraphicsLineItem(QLineF(a, l["handles_in"][k])); lo = QGraphicsLineItem(QLineF(a, l["handles_out"][k])); li.setPen(pen); lo.setPen(pen); li.setZValue(90); lo.setZValue(90); self.scene.addItem(li); self.scene.addItem(lo); self.edit_lines += [li, lo]

            for item in [BezierEditPoint(self, i, k, "handle_in", l["handles_in"][k], HANDLE_POINT_RADIUS, QColor(255,180,80)), BezierEditPoint(self, i, k, "handle_out", l["handles_out"][k], HANDLE_POINT_RADIUS, QColor(255,180,80)), BezierEditPoint(self, i, k, "anchor", a, ANCHOR_POINT_RADIUS, QColor("red"))]: self.scene.addItem(item); self.edit_items.append(item)

    def sync_edit_items_to_loop(self, i):

        if not (0 <= i < len(self.loops)): return

        l = self.loops[i]

        for item in self.edit_items:

            if getattr(item, "loop_index", None) != i: continue

            k = item.point_index

            if not (0 <= k < len(l["anchors"])): continue

            new_pos = l["anchors"][k] if item.kind == "anchor" else l["handles_in"][k] if item.kind == "handle_in" else l["handles_out"][k]

            if (item.pos() - new_pos).manhattanLength() > 1e-6: item.suppress_change = True; item.setPos(new_pos); item.suppress_change = False

        line_index = 0

        for k, a in enumerate(l["anchors"]):

            if line_index < len(self.edit_lines): self.edit_lines[line_index].setLine(QLineF(a, l["handles_in"][k])); line_index += 1

            if line_index < len(self.edit_lines): self.edit_lines[line_index].setLine(QLineF(a, l["handles_out"][k])); line_index += 1

    def select_loop(self, i):

        if i is None or not (0 <= i < len(self.loops)): self.selected_loop_index = None; self.selected_anchor_index = None; self.clear_edit_items(); self.update_loop_colors(); self.loop_selected_callback and self.loop_selected_callback(None); return

        self.selected_loop_index = i; self.selected_anchor_index = None; self.rebuild_edit_items(i); self.update_loop_colors(); self.loop_selected_callback and self.loop_selected_callback(i)

    def delete_selected_loop(self):

        if self.selected_loop_index is None: return

        self.push_undo_state(); l = self.loops[self.selected_loop_index]; self.scene.removeItem(l["item"]); self.scene.removeItem(l["label_item"]); self.loops.pop(self.selected_loop_index); self.selected_loop_index = None; self.update_loop_names_and_labels(); self.notify_loops_changed(); self.loop_selected_callback and self.loop_selected_callback(None)

    def update_loop_colors(self):

        for idx, l in enumerate(self.loops):

            l["item"].setBrush(QBrush(color_with_alpha(l.get("fill_color", DEFAULT_CURVE_COLOR), 96)))

            if idx == self.selected_loop_index: pen = QPen(QColor("yellow")); pen.setWidthF(SELECTED_CURVE_WIDTH); l["item"].setPen(pen); l["label_item"].setDefaultTextColor(SELECTED_LABEL_COLOR); continue

            color = QColor("blue") if l["type"] == "outer" else QColor("red") if l["type"] == "hole" else QColor("lime"); pen = QPen(color); pen.setWidthF(TYPE_CURVE_WIDTH if l["type"] in ("outer", "hole") else NORMAL_CURVE_WIDTH); l["item"].setPen(pen); l["label_item"].setDefaultTextColor(UNSELECTED_LABEL_COLOR)

    def get_loops_without_items(self): return [{"points": l["points"], "type": l["type"]} for l in self.loops]

    def notify_loops_changed(self): self.loops_changed_callback and self.loops_changed_callback()





class STLViewer(QWidget):

    def __init__(self, build_mesh_callback, get_unit_callback):

        super().__init__()

        self.build_mesh_callback = build_mesh_callback

        self.get_unit_callback = get_unit_callback

        self.view = None

        layout = QVBoxLayout(self)

        btn = QPushButton("Preview Current Model")

        btn.clicked.connect(self.preview_current_model)

        layout.addWidget(btn)

        try:

            import pyqtgraph as pg

            import pyqtgraph.opengl as gl

            self.pg = pg; self.gl = gl

            self.view = gl.GLViewWidget(); self.view.setBackgroundColor("black")

            layout.addWidget(self.view, 1)

        except Exception as e:

            layout.addWidget(QLabel("3D viewer unavailable: " + str(e)))



    def preview_current_model(self):

        if self.view is None: return

        try:

            mesh = self.build_mesh_callback(); self.view.clear()

            grid = self.gl.GLGridItem(); grid.setSize(x=100, y=100, z=1); grid.setSpacing(x=10, y=10, z=1); self.view.addItem(grid)

            item = self.gl.GLMeshItem(vertexes=np.asarray(mesh.vertices, float), faces=np.asarray(mesh.faces, int), faceColor=(.65,.72,1,.9), drawEdges=True, smooth=False)

            self.view.addItem(item)

            b = np.asarray(mesh.bounds, float); c = (b[0]+b[1])/2; size = max(b[1]-b[0]) or 100

            self.view.opts["center"] = self.pg.Vector(c[0], c[1], c[2]); self.view.setCameraPosition(distance=size*2.5, elevation=30, azimuth=45)

        except Exception as e: QMessageBox.critical(self, "Preview error", str(e))



class PDFViewer(QWidget):

    def __init__(self, preview_callback, save_callback, print_callback, page_type_changed_callback=None):

        super().__init__(); self.preview_callback=preview_callback; self.save_callback=save_callback; self.print_callback=print_callback; self.current_pdf_path=None; self.document=None

        layout=QVBoxLayout(self); top=QHBoxLayout(); self.page_type_combo=QComboBox(); self.page_type_combo.addItems(PDF_PAGE_TYPES)

        if page_type_changed_callback: self.page_type_combo.currentTextChanged.connect(page_type_changed_callback)

        prev=QPushButton("Preview in PDF viewer"); prev.clicked.connect(self.preview_pdf)

        save=QPushButton("Save PDF"); save.clicked.connect(self.save_callback)

        pr=QPushButton("Print"); pr.clicked.connect(self.print_current_pdf)

        for w in [QLabel("Paper:"), self.page_type_combo, prev, save, pr]: top.addWidget(w)

        top.addStretch(); layout.addLayout(top)

        if QPdfView is not None and QPdfDocument is not None:

            self.document=QPdfDocument(self); self.pdf_view=QPdfView(self); self.pdf_view.setDocument(self.document)

            try: self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage); self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

            except Exception: pass

            layout.addWidget(self.pdf_view, 1)

        else:

            lab=QLabel("PDF preview unavailable. Use Save PDF."); lab.setAlignment(Qt.AlignCenter); layout.addWidget(lab, 1)

    def set_page_type(self, v):

        if self.page_type_combo.currentText()!=v: self.page_type_combo.setCurrentText(v)

    def preview_pdf(self):

        p=self.preview_callback()

        if p: self.current_pdf_path=p; self.document.load(p) if self.document else QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def print_current_pdf(self):

        if not self.current_pdf_path: self.current_pdf_path=self.preview_callback()

        if self.current_pdf_path: self.print_callback(self.current_pdf_path)



class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__(); self.setWindowTitle("Image to STL Extruder"); self.resize(1400,850); self.current_project_path=None

        self.canvas=ImageCanvas(); self.loop_list=QListWidget()

        self.unit_combo=QComboBox(); self.unit_combo.addItems(["millimeter","inch"])

        self.scale_spin=QDoubleSpinBox(); self.scale_spin.setRange(.001,10000); self.scale_spin.setValue(1); self.scale_spin.setDecimals(4); self.scale_spin.setSuffix(" units / pixel")

        self.thickness_spin=QDoubleSpinBox(); self.thickness_spin.setRange(.001,10000); self.thickness_spin.setValue(5)

        self.illumination_diameter_spin=QDoubleSpinBox(); self.illumination_diameter_spin.setRange(.1,1000); self.illumination_diameter_spin.setValue(2); self.illumination_diameter_spin.setDecimals(3); self.illumination_diameter_spin.setSuffix(" mm")

        self.led_type_combo=QComboBox(); self.led_type_combo.addItems(LED_FOOTPRINTS)

        self.pdf_page_type_combo=QComboBox(); self.pdf_page_type_combo.addItems(PDF_PAGE_TYPES)

        self.label_size_spin=QDoubleSpinBox(); self.label_size_spin.setRange(.02,.5); self.label_size_spin.setValue(.15)

        self.threshold_spin=QSpinBox(); self.threshold_spin.setRange(0,255); self.threshold_spin.setValue(128)

        self.threshold_mode_combo=QComboBox(); self.threshold_mode_combo.addItems(["Dark shapes/lines","Light shapes/lines"])

        self.min_contour_area_spin=QDoubleSpinBox(); self.min_contour_area_spin.setRange(0,1e7); self.min_contour_area_spin.setValue(100)

        self.contour_simplify_spin=QDoubleSpinBox(); self.contour_simplify_spin.setRange(.1,1000); self.contour_simplify_spin.setValue(2)

        self.coordinate_label=QLabel("Cursor: -"); self.mode_label=QLabel("Mode: Select/Edit"); self.led_stats_label=QLabel("LED layout: not previewed")

        self.canvas.cursor_position_callback=self.update_cursor_label; self.canvas.loops_changed_callback=self.refresh_loop_list; self.canvas.loop_selected_callback=self.on_canvas_loop_selected; self.canvas.mode_changed_callback=self.update_mode_label

        self.unit_combo.currentTextChanged.connect(self.update_grid_settings); self.scale_spin.valueChanged.connect(self.update_grid_settings); self.label_size_spin.valueChanged.connect(lambda:self.canvas.set_label_font_factor(self.label_size_spin.value())); self.pdf_page_type_combo.currentTextChanged.connect(self.sync_pdf_page_type_to_viewer)

        def btn(t,f): b=QPushButton(t); b.clicked.connect(f); return b

        open_b=btn("Open Image",self.open_image); reset_b=btn("Reset View",self.reset_view); detect_b=btn("Detect Contours as Editable Curves",self.detect_contours)

        select_b=btn("Select/Edit Mode",lambda:self.canvas.set_edit_mode("select")); add_b=btn("Add Point Mode",lambda:self.canvas.set_edit_mode("add_point")); delpt_b=btn("Delete Point Mode",lambda:self.canvas.set_edit_mode("delete_point"))

        undo_b=btn("Undo Last Point",self.canvas.undo_last_point); dell_b=btn("Delete Selected Curve",self.canvas.delete_selected_loop); refresh_b=btn("Refresh Curve List",self.refresh_loop_list)

        border_b=btn("Set Selected as Border",self.set_selected_as_outer); hole_b=btn("Set Selected as Hole",self.set_selected_as_hole); preview_led_b=btn("Preview LED Layout",self.preview_led_layout)

        prev_stl_b=btn("Preview in STL Viewer",self.preview_in_viewer); exp_stl_b=btn("Export STL",self.export_stl); exp_kicad_b=btn("Export to KiCAD",self.export_kicad); prev_pdf_b=btn("Preview in PDF viewer",self.preview_in_pdf_viewer); save_pdf_b=btn("Save PDF",self.save_pdf)

        self.loop_list.currentRowChanged.connect(self.on_loop_list_selection_changed)

        settings_b=QPushButton("Settings"); settings_b.setCheckable(True); settings_b.clicked.connect(self.toggle_settings_group)

        self.settings_group=QGroupBox("Settings"); self.settings_group.setVisible(False); sl=QVBoxLayout(self.settings_group)

        for label,w in [("Units",self.unit_combo),("Scale",self.scale_spin),("Thickness",self.thickness_spin),("Illumination Diameter",self.illumination_diameter_spin),("LED Type",self.led_type_combo),("PDF Page Type",self.pdf_page_type_combo),("Curve Number Label Size",self.label_size_spin),("Threshold",self.threshold_spin),("Threshold Mode",self.threshold_mode_combo),("Minimum Contour Area",self.min_contour_area_spin),("Contour Simplify",self.contour_simplify_spin)]: sl.addWidget(QLabel(label)); sl.addWidget(w)

        side_panel=QWidget(); side=QVBoxLayout(side_panel)

        for w in [open_b,reset_b,settings_b,self.settings_group,self.coordinate_label,self.mode_label,QLabel("Image Contour Detection"),detect_b,QLabel("Curve Editing"),select_b,add_b,delpt_b,undo_b,dell_b,refresh_b,QLabel("Curves"),self.loop_list,border_b,hole_b,preview_led_b,self.led_stats_label,prev_stl_b,exp_stl_b,exp_kicad_b,prev_pdf_b,save_pdf_b]: side.addWidget(w)

        side.addStretch(); editor=QWidget(); el=QHBoxLayout(editor); el.addWidget(self.canvas,1); el.addWidget(side_panel)

        self.viewer=STLViewer(self.build_current_preview_mesh,self.get_current_unit_name); self.pdf_viewer=PDFViewer(self.create_pdf_preview,self.save_pdf,self.print_pdf_file,self.set_pdf_page_type_from_viewer)

        self.tabs=QTabWidget(); self.tabs.addTab(editor,"Image / Curves"); self.tabs.addTab(self.viewer,"STL Viewer"); self.tabs.addTab(self.pdf_viewer,"PDF Viewer"); self.setCentralWidget(self.tabs); self.create_menu()

    def sync_pdf_page_type_to_viewer(self,v): hasattr(self,"pdf_viewer") and self.pdf_viewer.set_page_type(v)

    def set_pdf_page_type_from_viewer(self,v):

        if self.pdf_page_type_combo.currentText()!=v: self.pdf_page_type_combo.setCurrentText(v)

    def create_menu(self):

        menu=self.menuBar().addMenu("File")

        for label,slot in [("Open Image",self.open_image),("Open Project",self.open_project),("Save Project",self.save_project),("Save Project As",self.save_project_as),("Export STL",self.export_stl),("Export to KiCAD",self.export_kicad),("Preview in PDF viewer",self.preview_in_pdf_viewer),("Save PDF",self.save_pdf)]: a=QAction(label,self); a.triggered.connect(slot); menu.addAction(a)

    def toggle_settings_group(self,checked): self.settings_group.setVisible(checked); self.sender() and self.sender().setText("Hide Settings" if checked else "Settings")

    def update_grid_settings(self): self.canvas.set_grid_settings(self.unit_combo.currentText(),self.scale_spin.value())

    def update_mode_label(self,mode): self.mode_label.setText({"select":"Mode: Select/Edit","add_point":"Mode: Add Point","delete_point":"Mode: Delete Point"}.get(mode,"Mode: Select/Edit"))

    def update_cursor_label(self,px,py,rx,ry): u="mm" if self.unit_combo.currentText()=="millimeter" else "in"; self.coordinate_label.setText(f"Cursor: px=({px:.1f}, {py:.1f}) | {u}=({rx:.3f}, {ry:.3f})")

    def on_canvas_loop_selected(self,i): self.loop_list.clearSelection() if i is None else (self.loop_list.setCurrentRow(i) if self.loop_list.currentRow()!=i else None)

    def on_loop_list_selection_changed(self,row): row>=0 and self.canvas.select_loop(row)

    def reset_view(self):

        if self.canvas.image_item is not None: self.canvas.fitInView(self.canvas.scene.sceneRect(),Qt.KeepAspectRatio); self.canvas.clear_all_except_image(True)

    def open_image(self):

        fp,_=QFileDialog.getOpenFileName(self,"Open image","","Images (*.png *.jpg *.jpeg *.bmp)")

        if fp:

            try: self.canvas.load_image(fp); self.update_grid_settings(); self.loop_list.clear(); self.current_project_path=None

            except Exception as e: QMessageBox.critical(self,"Error",str(e))

    def detect_contours(self): self.canvas.detect_contours_from_image(self.threshold_spin.value(),self.threshold_mode_combo.currentText(),self.min_contour_area_spin.value(),self.contour_simplify_spin.value())

    def refresh_loop_list(self):

        cur=self.canvas.selected_loop_index; self.loop_list.blockSignals(True); self.loop_list.clear(); [self.loop_list.addItem(f"{l['name']}: {l['type']} ({len(l.get('anchors',[]))} anchors, {len(l.get('points',[]))} STL points)") for l in self.canvas.loops]; self.loop_list.setCurrentRow(cur) if cur is not None and cur<self.loop_list.count() else None; self.loop_list.blockSignals(False)

    def selected_loop_index_from_list(self):

        r=self.loop_list.currentRow()

        if r<0: QMessageBox.warning(self,"No selection","Please select a curve first."); return None

        return r

    def style_selected_curve(self,i,typ):

        loop=self.canvas.loops[i]; default=DEFAULT_BORDER_COLOR if typ=="outer" else DEFAULT_HOLE_COLOR; cur=default if loop.get("type")!=typ else loop.get("fill_color",default); dlg=CurveStyleDialog(self,"Border Style" if typ=="outer" else "Segment Style",cur,loop.get("custom_name") or loop.get("name"),show_name=(typ=="hole"))

        if dlg.exec()!=QDialog.Accepted: return False

        self.canvas.push_undo_state(); loop["fill_color"]=dlg.color_hex();

        if typ=="hole": loop["custom_name"]=dlg.segment_name()

        return True

    def selected_loop_index_or_warn(self): return self.selected_loop_index_from_list()

    def set_selected_as_outer(self):

        i=self.selected_loop_index_from_list()

        if i is None or not self.style_selected_curve(i,"outer"): return

        for idx,l in enumerate(self.canvas.loops):

            if idx!=i and l["type"]=="outer": l["type"]="unassigned"

        self.canvas.loops[i]["type"]="outer"; self.canvas.update_loop_names_and_labels(); self.canvas.select_loop(i); self.refresh_loop_list(); self.loop_list.setCurrentRow(i); self.canvas.clear_error_arrows()

    def set_selected_as_hole(self):

        i=self.selected_loop_index_from_list()

        if i is None: return

        if not self.led_fits_loop_index(i):

            self.canvas.show_error_arrow_for_loop(i, "Selected LED does not fit")

            QMessageBox.warning(self, "LED does not fit", "The selected LED body is larger than this hole. Choose a smaller LED or enlarge the curve.")

            return

        if not self.style_selected_curve(i,"hole"): return

        self.canvas.loops[i]["type"]="hole"; self.canvas.update_loop_names_and_labels(); self.canvas.select_loop(i); self.refresh_loop_list(); self.loop_list.setCurrentRow(i); self.canvas.clear_error_arrows()

    def get_current_unit_name(self): return self.unit_combo.currentText()

    def build_current_preview_mesh(self):

        loops=self.canvas.get_loops_without_items()

        if sum(1 for l in loops if l["type"]=="outer")!=1: raise ValueError("Please define exactly one border curve before previewing.")

        return create_extruded_mesh(loops=loops,scale=self.scale_spin.value(),thickness=self.thickness_spin.value())

    def preview_in_viewer(self): self.tabs.setCurrentWidget(self.viewer); self.viewer.preview_current_model()

    def export_stl(self):

        loops=self.canvas.get_loops_without_items()

        if sum(1 for l in loops if l["type"]=="outer")!=1: QMessageBox.warning(self,"Invalid geometry","Please define exactly one border curve."); return

        fp,_=QFileDialog.getSaveFileName(self,"Save STL","","STL files (*.stl)")

        if not fp: return

        if not fp.lower().endswith(".stl"): fp+=".stl"

        try: create_extruded_stl(loops=loops,scale=self.scale_spin.value(),thickness=self.thickness_spin.value(),output_path=fp); QMessageBox.information(self,"Success",f"STL exported:\n{fp}")

        except Exception as e: QMessageBox.critical(self,"Export error",str(e))

    def project_dict(self): return {"version":1,"image_path":self.canvas.current_image_path,"settings":{"unit":self.unit_combo.currentText(),"scale":self.scale_spin.value(),"thickness":self.thickness_spin.value(),"illumination_diameter":self.illumination_diameter_spin.value(),"led_type":self.led_type_combo.currentText(),"pdf_page_type":self.pdf_page_type_combo.currentText(),"label_size":self.label_size_spin.value(),"threshold":self.threshold_spin.value(),"threshold_mode":self.threshold_mode_combo.currentText(),"min_contour_area":self.min_contour_area_spin.value(),"contour_simplify":self.contour_simplify_spin.value()},"canvas_state":self.canvas.serialize_state()}

    def save_project(self): self.write_project(self.current_project_path) if self.current_project_path else self.save_project_as()

    def save_project_as(self):

        default=Path(self.canvas.current_image_path).parent if self.canvas.current_image_path else Path.cwd(); fp,_=QFileDialog.getSaveFileName(self,"Save Project",str(default/"project.istlproj"),"Image STL Project (*.istlproj);;JSON (*.json)")

        if not fp: return

        if not fp.lower().endswith((".istlproj",".json")): fp+=".istlproj"

        self.current_project_path=fp; self.write_project(fp)

    def write_project(self,fp):

        try: Path(fp).write_text(json.dumps(self.project_dict(),indent=2),encoding="utf-8"); QMessageBox.information(self,"Project saved",f"Project saved:\n{fp}")

        except Exception as e: QMessageBox.critical(self,"Project save error",str(e))

    def open_project(self):

        fp,_=QFileDialog.getOpenFileName(self,"Open Project","","Image STL Project (*.istlproj *.json)")

        if not fp: return

        try:

            data=json.loads(Path(fp).read_text(encoding="utf-8")); img=data.get("image_path")

            if img:

                if not Path(img).exists(): img,_=QFileDialog.getOpenFileName(self,"Locate project image","","Images (*.png *.jpg *.jpeg *.bmp)")

                if img: self.canvas.load_image(img)

            st=data.get("settings",{}); self.unit_combo.setCurrentText(st.get("unit","millimeter")); self.scale_spin.setValue(float(st.get("scale",1))); self.thickness_spin.setValue(float(st.get("thickness",5))); self.illumination_diameter_spin.setValue(float(st.get("illumination_diameter",2))); self.led_type_combo.setCurrentText(st.get("led_type",LED_FOOTPRINTS[2])); self.pdf_page_type_combo.setCurrentText(st.get("pdf_page_type","Actual Size")); self.label_size_spin.setValue(float(st.get("label_size",.15))); self.threshold_spin.setValue(int(st.get("threshold",128))); self.threshold_mode_combo.setCurrentText(st.get("threshold_mode","Dark shapes/lines")); self.min_contour_area_spin.setValue(float(st.get("min_contour_area",100))); self.contour_simplify_spin.setValue(float(st.get("contour_simplify",2))); self.canvas.restore_state(data.get("canvas_state",{})); self.canvas.undo_stack=[]; self.update_grid_settings(); self.refresh_loop_list(); self.current_project_path=fp; QMessageBox.information(self,"Project opened",f"Project opened:\n{fp}")

        except Exception as e: QMessageBox.critical(self,"Project open error",str(e))



    def led_body_size_mm(self): return LED_BODY_SIZE_MM.get(self.led_type_combo.currentText(), (1.0, .5))

    def led_half_diagonal_mm(self):

        w,h=self.led_body_size_mm(); return math.hypot(w,h)/2

    def kicad_unit_factor_mm(self): return self.scale_spin.value() * (25.4 if self.unit_combo.currentText()=="inch" else 1.0)

    def polygon_area(self, pts): return 0.0 if len(pts)<3 else abs(sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts))))/2

    def polygon_centroid(self, pts):

        if len(pts)<3: return (sum(p[0] for p in pts)/max(len(pts),1), sum(p[1] for p in pts)/max(len(pts),1))

        a=cx=cy=0

        for i in range(len(pts)):

            x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]; cr=x1*y2-x2*y1; a+=cr; cx+=(x1+x2)*cr; cy+=(y1+y2)*cr

        a*=.5

        return (sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts)) if abs(a)<1e-9 else (cx/(6*a), cy/(6*a))

    def point_in_polygon(self, p, poly):

        x,y=p; inside=False; j=len(poly)-1

        for i in range(len(poly)):

            xi,yi=poly[i]; xj,yj=poly[j]

            if ((yi>y)!=(yj>y)) and (x < (xj-xi)*(y-yi)/((yj-yi) if yj!=yi else 1e-12)+xi): inside=not inside

            j=i

        return inside

    def point_to_polyline_distance(self, p, poly):

        px,py=p; best=1e99

        for i in range(len(poly)):

            ax,ay=poly[i]; bx,by=poly[(i+1)%len(poly)]; dx=bx-ax; dy=by-ay

            if dx==0 and dy==0: d=math.hypot(px-ax, py-ay)

            else: t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy))); d=math.hypot(px-(ax+t*dx), py-(ay+t*dy))

            best=min(best, d)

        return best

    def max_inscribed_candidate(self, poly):

        xs=[p[0] for p in poly]; ys=[p[1] for p in poly]

        minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)

        step=max(min(maxx-minx, maxy-miny)/35.0, 0.05)

        best=None; bestd=-1

        y=miny

        while y<=maxy:

            x=minx

            while x<=maxx:

                p=(x,y)

                if self.point_in_polygon(p, poly):

                    d=self.point_to_polyline_distance(p, poly)

                    if d>bestd: bestd=d; best=p

                x+=step

            y+=step

        c=self.polygon_centroid(poly)

        if self.point_in_polygon(c, poly):

            d=self.point_to_polyline_distance(c, poly)

            if d>bestd: bestd=d; best=c

        return best,bestd

    def led_fits_polygon(self, poly):

        _,d=self.max_inscribed_candidate(poly)

        return d >= self.led_half_diagonal_mm()

    def led_fits_loop_index(self, loop_index):

        if not (0 <= loop_index < len(self.canvas.loops)): return False

        scale=self.kicad_unit_factor_mm(); pts=[(x*scale,y*scale) for x,y in self.canvas.loops[loop_index].get("points",[])]

        return len(pts)>=3 and self.led_fits_polygon(pts)

    def estimate_segment_angle(self, pts):

        if len(pts)<2: return 0.0

        arr=np.array(pts,float); arr-=arr.mean(axis=0)

        try: _,_,vh=np.linalg.svd(arr, full_matrices=False); d=vh[0]; return norm_angle(math.degrees(math.atan2(d[1], d[0])))

        except Exception: return 0.0

    def candidate_fits_led(self, p, poly): return self.point_in_polygon(p, poly) and self.point_to_polyline_distance(p, poly) >= self.led_half_diagonal_mm()

    def calculate_led_positions_for_polygon(self, poly):

        # Coverage-driven placement.  Illumination is modeled as a circle centered on each LED.

        # We seed from the borders and refine uncovered interior sample points until coverage is complete or no legal center remains.

        if len(poly)<3 or not self.led_fits_polygon(poly): return []

        diameter=max(0.1, self.illumination_diameter_spin.value()); radius=diameter/2.0

        min_center_distance=radius  # previous minimum spacing request: half illumination diameter.

        led_clearance=self.led_half_diagonal_mm()

        xs=[p[0] for p in poly]; ys=[p[1] for p in poly]

        minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)

        width=maxx-minx; height=maxy-miny

        if width<=0 or height<=0: return []

        candidates=[]

        # Start near the border.  If the LED body allows it, first centers sit exactly at physical clearance from the curve boundary.

        pitch=max(radius*math.sqrt(2), led_clearance*2, 0.05)  # dense enough for square-grid circle coverage

        y=miny+led_clearance; row=0

        while y<=maxy-led_clearance+1e-9:

            x=minx+led_clearance+(pitch/2 if row%2 else 0)

            while x<=maxx-led_clearance+1e-9:

                p=(x,y)

                if self.candidate_fits_led(p, poly): candidates.append(p)

                x+=pitch

            y+=pitch

            row+=1

        # Add boundary-following candidates so narrow/curved regions get light from the edge inward.

        sample_step=max(radius/2.0, led_clearance, 0.05)

        for i in range(len(poly)):

            ax,ay=poly[i]; bx,by=poly[(i+1)%len(poly)]; seg_len=math.hypot(bx-ax, by-ay); n=max(1,int(seg_len/sample_step))

            for j in range(n+1):

                t=j/n; sx=ax+(bx-ax)*t; sy=ay+(by-ay)*t

                # Probe around boundary point; keep any legal center.  This handles concave and oddly shaped holes.

                for ang in np.linspace(0, 2*math.pi, 12, endpoint=False):

                    p=(sx+math.cos(ang)*led_clearance, sy+math.sin(ang)*led_clearance)

                    if self.candidate_fits_led(p, poly): candidates.append(p)

        best,d=self.max_inscribed_candidate(poly)

        if best and d>=led_clearance: candidates.insert(0,best)

        # Unique candidates

        uniq=[]; seen=set()

        for p in candidates:

            key=(round(p[0],3), round(p[1],3))

            if key not in seen: seen.add(key); uniq.append(p)

        cx,cy=self.polygon_centroid(poly)

        uniq.sort(key=lambda p: (self.point_to_polyline_distance(p, poly), -((p[0]-cx)**2+(p[1]-cy)**2)))

        uniq=list(reversed(uniq))

        chosen=[]

        def far_enough(p): return all(math.hypot(p[0]-q[0], p[1]-q[1]) >= min_center_distance for q in chosen)

        for p in uniq:

            if far_enough(p): chosen.append(p)

        if not chosen and best and d>=led_clearance: chosen=[best]

        # Coverage refinement: sample the polygon interior and add LEDs near any uncovered point.

        cover_step=max(radius/2.0, min(width,height)/45.0, 0.05)

        samples=[]; y=miny

        while y<=maxy+1e-9:

            x=minx

            while x<=maxx+1e-9:

                p=(x,y)

                if self.point_in_polygon(p, poly): samples.append(p)

                x+=cover_step

            y+=cover_step

        # Greedy add: for each uncovered sample, add the candidate that covers most currently uncovered samples.

        for _ in range(500):

            uncovered=[s for s in samples if not chosen or min(math.hypot(s[0]-c[0], s[1]-c[1]) for c in chosen) > radius]

            if not uncovered: break

            legal=[p for p in uniq if far_enough(p) and p not in chosen]

            if not legal: break

            uset=uncovered

            bestp=max(legal, key=lambda p: sum(1 for s in uset if math.hypot(s[0]-p[0], s[1]-p[1]) <= radius))

            if sum(1 for s in uset if math.hypot(s[0]-bestp[0], s[1]-bestp[1]) <= radius)==0: break

            chosen.append(bestp)

        return chosen



    def led_coverage_stats_for_polygon(self, poly, leds):

        diameter = max(0.1, self.illumination_diameter_spin.value())

        radius = diameter / 2.0

        area = self.polygon_area(poly)

        if len(poly) < 3 or area <= 0:

            return {"coverage": 0.0, "covered": 0, "samples": 0, "area": 0.0, "density": 0.0}

        xs=[p[0] for p in poly]; ys=[p[1] for p in poly]

        minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)

        # Sample grid is for preview/statistics only, not manufacturing export.

        step=max(radius/3.0, min(maxx-minx, maxy-miny)/60.0, 0.05)

        covered=0; samples=0

        y=miny

        while y<=maxy+1e-9:

            x=minx

            while x<=maxx+1e-9:

                pt=(x,y)

                if self.point_in_polygon(pt, poly):

                    samples += 1

                    if leds and min(math.hypot(pt[0]-l[0], pt[1]-l[1]) for l in leds) <= radius:

                        covered += 1

                x += step

            y += step

        coverage=(covered/samples*100.0) if samples else 0.0

        density=(len(leds)/area*100.0) if area>0 else 0.0

        return {"coverage": coverage, "covered": covered, "samples": samples, "area": area, "density": density}



    def density_color(self, overlap_count, coverage):

        # Blue = sparse / low overlap, Green = normal, Orange/Red = high overlap density.

        if coverage < 85:

            return QColor(60, 120, 255, 70)

        if overlap_count <= 1:

            return QColor(0, 210, 90, 70)

        if overlap_count == 2:

            return QColor(255, 170, 0, 75)

        return QColor(255, 40, 40, 85)



    def preview_led_layout(self):

        self.canvas.clear_led_preview()

        holes=[l for l in self.canvas.loops if l["type"]=="hole"]

        if not holes:

            self.led_stats_label.setText("LED layout: no holes")

            QMessageBox.information(self,"LED layout","No holes/segments are defined yet.")

            return

        scale=self.kicad_unit_factor_mm()

        if scale <= 0:

            QMessageBox.warning(self,"Scale error","Scale must be greater than zero.")

            return

        radius_mm=max(0.1,self.illumination_diameter_spin.value())/2.0

        body_w_mm, body_h_mm=self.led_body_size_mm()

        total_leds=0; weighted_coverage=0.0; total_area=0.0; segment_lines=[]

        for loop in holes:

            poly=[(x*scale,y*scale) for x,y in loop.get("points",[])]

            if len(poly)<3:

                continue

            leds=self.calculate_led_positions_for_polygon(poly)

            stats=self.led_coverage_stats_for_polygon(poly, leds)

            total_leds += len(leds); weighted_coverage += stats["coverage"]*stats["area"]; total_area += stats["area"]

            angle=self.estimate_segment_angle(poly)

            # Draw LED illumination circles and body markers in scene/pixel coordinates.

            for led in leds:

                overlaps=sum(1 for other in leds if math.hypot(led[0]-other[0], led[1]-other[1]) <= radius_mm*2.0) - 1

                color=self.density_color(overlaps, stats["coverage"])

                cx=led[0]/scale; cy=led[1]/scale

                tooltip=f"{loop['name']} | LED center=({led[0]:.2f}, {led[1]:.2f}) mm | overlaps={overlaps} | coverage={stats['coverage']:.1f}%"

                self.canvas.add_led_preview_circle((cx,cy), radius_mm/scale, color, tooltip)

                self.canvas.add_led_preview_body((cx,cy), max(body_w_mm/scale, 1.0), max(body_h_mm/scale, 1.0), angle, QColor(255,255,255,220), tooltip)

            # Add segment label near centroid.

            centroid=self.polygon_centroid(poly)

            self.canvas.add_led_preview_text(f"{loop['name']}: {len(leds)} LED | {stats['coverage']:.1f}%", (centroid[0]/scale, centroid[1]/scale))

            segment_lines.append(f"{loop['name']}: {len(leds)} LED, {stats['coverage']:.1f}% coverage, density {stats['density']:.2f} LED/100mm²")

        overall=(weighted_coverage/total_area) if total_area>0 else 0.0

        self.led_stats_label.setText(f"LED layout: {total_leds} LEDs | {overall:.1f}% coverage")

        QMessageBox.information(self,"LED layout preview", "\n".join([f"Total LEDs: {total_leds}", f"Weighted coverage: {overall:.1f}%", "", *segment_lines]))



    def validate_pdf_geometry(self):

        outer=[l for l in self.canvas.loops if l["type"]=="outer"]; holes=[l for l in self.canvas.loops if l["type"]=="hole"]

        if len(outer)!=1: raise ValueError("Please define exactly one Border before saving PDF.")

        if not outer[0].get("points"): raise ValueError("Border curve has no points.")

        return outer[0], holes

    def get_pdf_default_path(self): return (Path(self.canvas.current_image_path).parent/f"{Path(self.canvas.current_image_path).stem}.pdf") if self.canvas.current_image_path else Path.cwd()/"image_to_stl_export.pdf"

    def create_pdf_preview(self):

        try: o,h=self.validate_pdf_geometry(); p=Path(tempfile.gettempdir())/"image_to_stl_pdf_preview.pdf"; self.create_dimension_pdf(str(p), o, h); return str(p)

        except Exception as e: QMessageBox.critical(self,"PDF preview error",str(e)); return None

    def preview_in_pdf_viewer(self): self.tabs.setCurrentWidget(self.pdf_viewer); self.pdf_viewer.preview_pdf()

    def save_pdf(self):

        try: o,h=self.validate_pdf_geometry()

        except Exception as e: QMessageBox.warning(self,"PDF export error",str(e)); return

        fp,_=QFileDialog.getSaveFileName(self,"Save PDF",str(self.get_pdf_default_path()),"PDF files (*.pdf)")

        if not fp: return

        if not fp.lower().endswith(".pdf"): fp+=".pdf"

        try: self.create_dimension_pdf(fp,o,h); QMessageBox.information(self,"PDF saved",f"PDF exported:\n{fp}"); self.pdf_viewer.document and self.pdf_viewer.document.load(fp)

        except Exception as e: QMessageBox.critical(self,"PDF export error",str(e))

    def print_pdf_file(self,path): QDesktopServices.openUrl(QUrl.fromLocalFile(path)) if path else None

    def make_reportlab_color(self,hx):

        from reportlab.lib.colors import Color

        c=QColor(hx or DEFAULT_HOLE_COLOR); return Color(c.red()/255, c.green()/255, c.blue()/255)

    def pdf_page_size_points(self,dw,dh,unit_factor,margin):

        page=self.pdf_page_type_combo.currentText()

        if page=="Actual Size": return ((dw+2*margin)*unit_factor, (dh+2*margin)*unit_factor, margin, margin)

        from reportlab.lib.units import mm

        w,h=(210,297) if "A4" in page else (148,210)

        if "Landscape" in page: w,h=h,w

        return w*mm,h*mm,margin,margin

    def get_segment_led_data_mm(self):

        scale=self.kicad_unit_factor_mm(); out=[]

        for l in [x for x in self.canvas.loops if x["type"]=="hole"]:

            pts=[(x*scale, y*scale) for x,y in l.get("points",[])]

            if len(pts)>=3: out.append({"loop":l,"points_mm":pts,"leds_mm":self.calculate_led_positions_for_polygon(pts),"angle":self.estimate_segment_angle(pts)})

        return out

    def create_dimension_pdf(self,output_path,outer_loop,hole_loops):

        from reportlab.pdfgen import canvas as pdf_canvas

        from reportlab.lib.units import mm, inch

        from reportlab.lib.colors import black, green, Color

        unit=self.unit_combo.currentText(); upp=self.scale_spin.value(); unit_factor=mm if unit=="millimeter" else inch; us="mm" if unit=="millimeter" else "in"; margin=10 if unit=="millimeter" else .4

        def real(l): return [(x*upp,y*upp) for x,y in l.get("points",[])]

        outer=real(outer_loop); holes=[(l,real(l)) for l in hole_loops if len(real(l))>=3]; allp=outer+[p for _,pts in holes for p in pts]; minx,maxx=min(p[0] for p in allp),max(p[0] for p in allp); miny,maxy=min(p[1] for p in allp),max(p[1] for p in allp); dw=maxx-minx; dh=maxy-miny

        page_w,page_h,mx,my=self.pdf_page_size_points(dw,dh,unit_factor,margin); pdf=pdf_canvas.Canvas(output_path,pagesize=(page_w,page_h)); draw_w=dw*unit_factor; draw_h=dh*unit_factor; ox=(page_w-draw_w)/2; oy=(page_h-draw_h)/2

        if self.pdf_page_type_combo.currentText()=="Actual Size": ox=mx*unit_factor; oy=my*unit_factor

        if ox<0 or oy<0: raise ValueError(f"Drawing is larger than {self.pdf_page_type_combo.currentText()}; choose Actual Size or larger paper.")

        def pdfpt(p): x,y=p; return ox+(x-minx)*unit_factor, oy+(maxy-y)*unit_factor

        def path(pts):

            pa=pdf.beginPath(); x,y=pdfpt(pts[0]); pa.moveTo(x,y)

            for pt in pts[1:]: x,y=pdfpt(pt); pa.lineTo(x,y)

            pa.close(); return pa

        def step(length): return self.canvas.nice_number(max(length/10,1e-9))

        def rulers():

            st=step(max(dw,dh)); pdf.setStrokeColor(Color(.75,.75,.75)); pdf.setLineWidth(.15); pdf.setFont("Helvetica",6); pdf.setFillColor(black); gx=math.floor(minx/st)*st

            while gx<=maxx+1e-9:

                x1,y1=pdfpt((gx,miny)); x2,y2=pdfpt((gx,maxy)); pdf.line(x1,y1,x2,y2); sec=gx/25.4 if us=="mm" else gx*25.4; pdf.drawString(x1+1, oy+draw_h+6, f"{gx:.3g}{us}/{sec:.3g}{'in' if us=='mm' else 'mm'}"); gx+=st

            gy=math.floor(miny/st)*st

            while gy<=maxy+1e-9:

                x1,y1=pdfpt((minx,gy)); x2,y2=pdfpt((maxx,gy)); pdf.line(x1,y1,x2,y2); sec=gy/25.4 if us=="mm" else gy*25.4; pdf.drawString(2,y1+1,f"{gy:.3g}{us}/{sec:.3g}{'in' if us=='mm' else 'mm'}"); gy+=st

            pdf.setStrokeColor(black); pdf.setLineWidth(.5); pdf.rect(ox,oy,draw_w,draw_h,stroke=1,fill=0)

        def rotated_rect(cx,cy,w,h,angle): pdf.saveState(); pdf.translate(cx,cy); pdf.rotate(-angle); pdf.rect(-w/2,-h/2,w,h,stroke=1,fill=1); pdf.restoreState()

        def page(with_leds=False):

            rulers(); pdf.setFillColor(self.make_reportlab_color(outer_loop.get("fill_color",DEFAULT_BORDER_COLOR))); pdf.setStrokeColor(black); pdf.drawPath(path(outer),stroke=1,fill=1)

            for l,pts in holes: pdf.setFillColor(self.make_reportlab_color(l.get("fill_color",DEFAULT_HOLE_COLOR))); pdf.drawPath(path(pts),stroke=1,fill=1)

            if with_leds:

                scale=self.kicad_unit_factor_mm(); lw,lh=self.led_body_size_mm(); pdf.setFillColor(green); pdf.setStrokeColor(green)

                for item in self.get_segment_led_data_mm():

                    for lx,ly in item["leds_mm"]:

                        rx=lx/scale*upp if scale else lx; ry=ly/scale*upp if scale else ly; cx,cy=pdfpt((rx,ry)); rotated_rect(cx,cy,(lw/scale*upp if scale else lw)*unit_factor,(lh/scale*upp if scale else lh)*unit_factor,item["angle"])

            pdf.setFillColor(black); pdf.setFont("Helvetica",8); pdf.drawString(max(2,ox),max(2,oy-12),f"Size: {dw:.3f} {us} x {dh:.3f} {us} | Page: {self.pdf_page_type_combo.currentText()} | Print at 100% / actual size")

        page(False); pdf.showPage(); page(True); pdf.showPage(); pdf.save()

    def kicad_escape(self,t): return str(t).replace("\\","\\\\").replace('"','\\"')

    def make_kicad_transform(self,loops):

        s=self.kicad_unit_factor_mm(); pts=[(x*s,y*s) for l in loops for x,y in l.get("points",[])]

        if not pts: return lambda p:(0,0)

        minx=min(x for x,y in pts); miny=min(y for x,y in pts); return lambda p:(p[0]*s-minx+10,p[1]*s-miny+10)

    def get_kicad_led_items(self,segs,transform):

        items=[]; n=1

        for si,l in enumerate(segs,1):

            pts=[transform(p) for p in l["points"]]; leds=self.calculate_led_positions_for_polygon(pts); angle=self.estimate_segment_angle(pts)

            for p in leds:

                su=str(uuid.uuid4()); items.append({"ref":f"D{n}","value":l["name"],"segment_index":si,"loop":l,"x":p[0],"y":p[1],"angle":angle,"net":n,"net_name":f"Net-({l['name']}-{n})","symbol_uuid":su,"path":"/"+su}); n+=1

        return items

    def create_kicad_aligned_stl(self,stl,border,segs,transform,thick):

        from shapely.geometry import Polygon

        import trimesh

        outer=[transform(p) for p in border["points"]]; holes=[[transform(p) for p in l["points"]] for l in segs]

        if outer and outer[0]!=outer[-1]: outer.append(outer[0])

        for h in holes:

            if h and h[0]!=h[-1]: h.append(h[0])

        poly=Polygon(shell=outer, holes=holes)

        if not poly.is_valid or poly.area<=0: poly=poly.buffer(0)

        trimesh.creation.extrude_polygon(poly,height=thick).export(str(stl))

    def write_kicad_project_file(self,pro): pro.write_text(json.dumps({"meta":{"filename":pro.name,"version":1},"board":{"design_settings":{"defaults":{},"rules":{}}},"libraries":{"pinned_footprint_libs":[],"pinned_symbol_libs":[]}},indent=2),encoding="utf-8")

    def schematic_layout_transform(self,segs,transform,led_items):

        all_pts=[transform(p) for l in segs for p in l.get("points",[])] + [(it["x"],it["y"]) for it in led_items]

        if not all_pts: return lambda p:p

        minx,maxx=min(x for x,y in all_pts),max(x for x,y in all_pts); miny,maxy=min(y for x,y in all_pts),max(y for x,y in all_pts); fit_scale=min(220/max(maxx-minx,1),150/max(maxy-miny,1))

        return lambda p:(20+(p[0]-minx)*fit_scale,20+(p[1]-miny)*fit_scale)

    def add_schematic_curve(self,lines,points):

        if len(points)<2: return

        used=points[::max(1,len(points)//80)]

        if used[0]!=used[-1]: used=used+[used[0]]

        for i in range(len(used)-1):

            x0,y0=used[i]; x3,y3=used[i+1]; x1=x0+(x3-x0)/3; y1=y0+(y3-y0)/3; x2=x0+2*(x3-x0)/3; y2=y0+2*(y3-y0)/3

            lines.append(f'  (bezier (pts (xy {x0:.3f} {y0:.3f}) (xy {x1:.3f} {y1:.3f}) (xy {x2:.3f} {y2:.3f}) (xy {x3:.3f} {y3:.3f})) (stroke (width 0.15) (type solid)) (fill (type none)) (uuid "{uuid.uuid4()}"))')

    def write_kicad_schematic_file(self,sch,segs,transform,led_items):

        fp=self.kicad_escape(self.led_type_combo.currentText()); st=self.schematic_layout_transform(segs,transform,led_items)

        lines=[f'(kicad_sch (version {KICAD_FILE_VERSION}) (generator "image_to_stl_app_release")',f'  (uuid "{uuid.uuid4()}")','  (paper "A4")','  (lib_symbols','    (symbol "Device:LED" (pin_numbers hide) (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)','      (property "Reference" "D" (at 0 2.54 0) (effects (font (size 1.27 1.27))))','      (property "Value" "LED" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))',f'      (property "Footprint" "{fp}" (at 0 -5.08 0) (effects (font (size 1.27 1.27)) hide))','      (symbol "LED_0_1")','      (symbol "LED_1_1"','        (pin passive line (at -3.81 0 0) (length 2.54) (name "K" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))','        (pin passive line (at 3.81 0 180) (length 2.54) (name "A" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))','      )','    )','  )']

        for l in segs: self.add_schematic_curve(lines,[st(transform(p)) for p in l["points"]])

        inst=[]

        for it in led_items:

            sx,sy=st((it["x"],it["y"])); angle=min([0,90,180,270], key=lambda a: abs((it["angle"]%360)-a)); ref=self.kicad_escape(it["ref"]); val=self.kicad_escape(it["value"]); su=it["symbol_uuid"]

            lines += [f'  (symbol (lib_id "Device:LED") (at {sx:.3f} {sy:.3f} {angle}) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes)',f'    (uuid "{su}")',f'    (property "Reference" "{ref}" (at {sx:.3f} {sy-4.5:.3f} {angle}) (effects (font (size 1.27 1.27))))',f'    (property "Value" "{val}" (at {sx:.3f} {sy+4.5:.3f} {angle}) (effects (font (size 1.27 1.27))))',f'    (property "Footprint" "{fp}" (at {sx:.3f} {sy+7:.3f} {angle}) (effects (font (size 1.27 1.27)) hide))','  )']; inst.append((su,ref,val))

        lines += ['  (sheet_instances','    (path "/" (page "1"))','  )','  (symbol_instances']

        for su,ref,val in inst: lines.append(f'    (path "/{su}" (reference "{ref}") (unit 1) (value "{val}") (footprint "{fp}"))')

        lines += ['  )',')']; sch.write_text('\n'.join(lines),encoding="utf-8")

    def add_kicad_curve_lines(self,lines,points,transform,layer,width):

        pts=[transform(p) for p in points]

        for i in range(len(pts)):

            x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]

            if abs(x1-x2)<.001 and abs(y1-y2)<.001: continue

            lines.append(f'  (gr_line (start {x1:.4f} {y1:.4f}) (end {x2:.4f} {y2:.4f}) (stroke (width {width:.4f}) (type solid)) (layer "{layer}") (uuid "{uuid.uuid4()}"))')

    def footprint_search_dirs(self):

        dirs=[Path(v) for k,v in os.environ.items() if "FOOTPRINT" in k.upper() and v]

        dirs += [Path(p) for p in ["/usr/share/kicad/footprints","/usr/local/share/kicad/footprints","/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints","C:/Program Files/KiCad/10.0/share/kicad/footprints","C:/Program Files/KiCad/9.0/share/kicad/footprints","C:/Program Files/KiCad/8.0/share/kicad/footprints"]]

        return dirs

    def find_official_footprint_file(self,fp):

        lib,name=fp.split(":",1)

        for d in self.footprint_search_dirs():

            p=d/f"{lib}.pretty"/f"{name}.kicad_mod"

            if p.exists(): return p

        return None

    def official_footprint_instance(self,fp,it):

        path=self.find_official_footprint_file(fp)

        if not path: return None

        txt=path.read_text(encoding="utf-8",errors="ignore"); txt=re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{uuid.uuid4()}")', txt); lines=txt.splitlines()

        if not lines: return None

        lines[0]=f'  (footprint "{self.kicad_escape(fp)}" (layer "F.Cu")'; insert=[f'    (uuid "{uuid.uuid4()}")',f'    (at {it["x"]:.4f} {it["y"]:.4f} {it["angle"]:.1f})',f'    (path "{it["path"]}")']

        for j,line in enumerate(insert,1): lines.insert(j,line)

        return "\n".join(lines)

    def fallback_footprint_instance(self,fp,it):

        pad_w,pad_h,pad_dx=LED_PAD_FALLBACK.get(fp,LED_PAD_FALLBACK["LED_SMD:LED_0402_1005Metric"]); lw,lh=self.led_body_size_mm(); ref=self.kicad_escape(it['ref']); val=self.kicad_escape(it['value']); net=self.kicad_escape(it['net_name'])

        return "\n".join([f'  (footprint "{self.kicad_escape(fp)}" (layer "F.Cu")',f'    (uuid "{uuid.uuid4()}")',f'    (at {it["x"]:.4f} {it["y"]:.4f} {it["angle"]:.1f})',f'    (path "{it["path"]}")','    (attr smd)',f'    (property "Reference" "{ref}" (at 0 {-lh:.3f} 0) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))',f'    (property "Value" "{val}" (at 0 {lh:.3f} 0) (layer "F.Fab") (effects (font (size 0.5 0.5) (thickness 0.08))))',f'    (fp_rect (start {-lw/2:.4f} {-lh/2:.4f}) (end {lw/2:.4f} {lh/2:.4f}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.Fab"))',f'    (pad "1" smd roundrect (at {-pad_dx:.4f} 0) (size {pad_w:.4f} {pad_h:.4f}) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25) (net {it["net"]} "{net}") (pinfunction "K") (pintype "passive"))',f'    (pad "2" smd roundrect (at {pad_dx:.4f} 0) (size {pad_w:.4f} {pad_h:.4f}) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25) (net {it["net"]} "{net}") (pinfunction "A") (pintype "passive"))','  )'])

    def write_kicad_pcb_file(self,pcb,border,segs,transform,stl_name,led_items):

        lines=[f'(kicad_pcb (version {KICAD_FILE_VERSION}) (generator "image_to_stl_app_release")','  (general','    (thickness 1.6)','  )','  (paper "A4")','  (layers','    (0 "F.Cu" signal)','    (31 "B.Cu" signal)','    (37 "F.SilkS" user "F.Silkscreen")','    (39 "F.Mask" user)','    (44 "Edge.Cuts" user)','  )','  (setup','    (pad_to_mask_clearance 0)','  )','  (net 0 "")']

        for it in led_items: lines.append(f'  (net {it["net"]} "{self.kicad_escape(it["net_name"])}")')

        self.add_kicad_curve_lines(lines,border["points"],transform,"Edge.Cuts",0.1)

        for l in segs: self.add_kicad_curve_lines(lines,l["points"],transform,"F.SilkS",0.12)

        fp=self.led_type_combo.currentText(); used_fallback=False

        for it in led_items:

            block=self.official_footprint_instance(fp,it)

            if block is None: used_fallback=True; block=self.fallback_footprint_instance(fp,it)

            lines.append(block)

        lines += ['  (footprint "ImageToSTL:Generated_3D_Model" (layer "F.Cu")',f'    (uuid "{uuid.uuid4()}")','    (at 0 0 0)','    (attr exclude_from_pos_files exclude_from_bom)','    (fp_text reference "MODEL1" (at 0 0 0) (layer "F.SilkS") hide (effects (font (size 1 1) (thickness 0.15))))','    (fp_text value "Generated STL Model" (at 0 2 0) (layer "F.Fab") hide (effects (font (size 1 1) (thickness 0.15))))',f'    (model "${{KIPRJMOD}}/{self.kicad_escape(stl_name)}"','      (offset (xyz 0 0 0))','      (scale (xyz 1 1 1))','      (rotate (xyz 0 0 0))','    )','  )',')']

        pcb.write_text('\n'.join(lines),encoding="utf-8"); return used_fallback

    def write_kicad_project_file(self,pro): pro.write_text(json.dumps({"meta":{"filename":pro.name,"version":1},"board":{"design_settings":{"defaults":{},"rules":{}}},"libraries":{"pinned_footprint_libs":[],"pinned_symbol_libs":[]}},indent=2),encoding="utf-8")

    def create_kicad_aligned_stl(self,stl,border,segs,transform,thick):

        from shapely.geometry import Polygon

        import trimesh

        outer=[transform(p) for p in border["points"]]; holes=[[transform(p) for p in l["points"]] for l in segs]

        if outer and outer[0]!=outer[-1]: outer.append(outer[0])

        for h in holes:

            if h and h[0]!=h[-1]: h.append(h[0])

        poly=Polygon(shell=outer,holes=holes)

        if not poly.is_valid or poly.area<=0: poly=poly.buffer(0)

        trimesh.creation.extrude_polygon(poly,height=thick).export(str(stl))

    def export_kicad(self):

        loops=self.canvas.loops; borders=[l for l in loops if l['type']=='outer']; segs=[l for l in loops if l['type']=='hole']

        if len(borders)!=1: QMessageBox.warning(self,'KiCad export error','Please define exactly one Border before exporting to KiCad.'); return

        if not segs: QMessageBox.warning(self,'KiCad export error','Please define at least one Segment/Hole before exporting to KiCad.'); return

        try:

            if self.canvas.current_image_path: ip=Path(self.canvas.current_image_path); name=ip.stem; outdir=ip.parent/name

            else: name='image_to_kicad_project'; outdir=Path.cwd()/name

            outdir.mkdir(parents=True,exist_ok=True); pro=outdir/f'{name}.kicad_pro'; sch=outdir/f'{name}.kicad_sch'; pcb=outdir/f'{name}.kicad_pcb'; stl=outdir/f'{name}_3d_model.stl'; transform=self.make_kicad_transform(loops); thick=self.thickness_spin.value()*(25.4 if self.unit_combo.currentText()=='inch' else 1); self.create_kicad_aligned_stl(stl,borders[0],segs,transform,thick); led_items=self.get_kicad_led_items(segs,transform); self.write_kicad_project_file(pro); self.write_kicad_schematic_file(sch,segs,transform,led_items); fallback=self.write_kicad_pcb_file(pcb,borders[0],segs,transform,stl.name,led_items); msg=f'KiCad project exported:\n{outdir}' + ('\n\nWarning: official local KiCad footprint file was not found, so valid fallback pad geometry was embedded.' if fallback else '\n\nOfficial KiCad library footprint geometry was embedded from your local KiCad installation.'); QMessageBox.information(self,'KiCad export complete',msg)

        except Exception as e: QMessageBox.critical(self,'KiCad export error',str(e))



def main():

    app=QApplication(sys.argv); window=MainWindow(); window.show(); sys.exit(app.exec())

if __name__=='__main__':

    try: main()

    except Exception:

        err=traceback.format_exc(); print('\nAPPLICATION CRASHED'); print(err); open('crash_log.txt','w',encoding='utf-8').write(err); input('Press Enter to close...')

