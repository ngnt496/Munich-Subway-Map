"""Hộp thoại xác thực quyền Admin để quản lý đóng/mở tuyến và ga tàu."""

import customtkinter as ctk


class AdminLoginDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_login_success, verify_callback):
        super().__init__(parent)
        self.parent = parent
        self.on_login_success = on_login_success
        self.verify_callback = verify_callback

        self.title("Xác thực Quản trị viên (Admin Login)")
        self.geometry("380x280")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Tiêu đề
        self.lbl_title = ctk.CTkLabel(
            self,
            text="Yêu cầu quyền Admin",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.lbl_title.pack(padx=20, pady=(20, 5), anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            self,
            text="Vui lòng đăng nhập để thực hiện đóng / mở ga hoặc tuyến tàu.",
            wraplength=340,
            justify="left",
            font=ctk.CTkFont(size=12),
        )
        self.lbl_subtitle.pack(padx=20, pady=(0, 15), anchor="w")

        # Form đăng nhập
        self.entry_username = ctk.CTkEntry(self, placeholder_text="Tài khoản", width=340)
        self.entry_username.pack(padx=20, pady=(0, 10))
        self.entry_username.focus_set()

        self.entry_password = ctk.CTkEntry(self, placeholder_text="Mật khẩu", show="*", width=340)
        self.entry_password.pack(padx=20, pady=(0, 10))
        self.entry_password.bind("<Return>", lambda event: self._handle_submit())

        # Thông báo lỗi
        self.lbl_error = ctk.CTkLabel(
            self,
            text="",
            text_color="#db4437",
            font=ctk.CTkFont(size=12),
        )
        self.lbl_error.pack(padx=20, pady=(0, 10), anchor="w")

        # Nút bấm
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        self.btn_login = ctk.CTkButton(
            self.btn_frame,
            text="Đăng nhập",
            command=self._handle_submit,
            fg_color="#3b8ed0",
            width=110,
        )
        self.btn_login.pack(side="right", padx=(10, 0))

        self.btn_cancel = ctk.CTkButton(
            self.btn_frame,
            text="Hủy",
            command=self.destroy,
            fg_color="#5f6368",
            width=80,
        )
        self.btn_cancel.pack(side="right")

    def _handle_submit(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()

        if not username or not password:
            self.lbl_error.configure(text="Vui lòng nhập đầy đủ tài khoản và mật khẩu.")
            return

        is_valid = self.verify_callback(username, password)
        if is_valid:
            self.destroy()
            if self.on_login_success:
                self.on_login_success()
        else:
            self.lbl_error.configure(text="Tài khoản hoặc mật khẩu không chính xác!")
            self.entry_password.delete(0, "end")

