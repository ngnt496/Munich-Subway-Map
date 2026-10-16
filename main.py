"""Điểm khởi chạy ứng dụng tìm đường tàu điện ngầm Munich U-Bahn (Munich Subway Map)."""

import sys

# Cấu hình UTF-8 an toàn cho console Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from controllers.app_controller import AppController
from services.map_service import MapService
from views.window import MunichNavigationApp


def main():
    # 1. Khởi tạo Service nạp bản đồ
    map_service = MapService()

    # 2. Khởi tạo Giao diện View
    view = MunichNavigationApp()

    # 3. Khởi tạo Controller điều phối (truyền cấu hình tài khoản admin từ config)
    controller = AppController(
        view=view,
        map_service=map_service,
        admin_credentials=config.ADMIN_CREDENTIALS,
    )
    view.set_controller(controller)

    # 4. Tải dữ liệu ban đầu và khởi chạy giao diện
    controller.initialize()
    view.mainloop()


if __name__ == "__main__":
    main()
