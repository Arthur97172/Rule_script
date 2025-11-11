import tkinter as tk
from tkinter import messagebox, scrolledtext
import datetime
import platform
import uuid
import os
import base64

# 需要安装：pip install cryptography
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

# --- 密钥配置 (与 key_utils.py 保持一致) ---
PRIVATE_KEY_PASSWORD = b"SVIEW_BY_ARTHUR_GU"
PRIVATE_KEY_FILE = "private_key.pem"
# --- 配置结束 ---

# ----------------------------------------------------
# 核心工具函数 (从 license_utils.py 复制并整合)
# ----------------------------------------------------

def get_machine_id():
    """生成一个稳定的机器唯一标识符 (基于 MAC 地址)。"""
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0, 8 * 6, 8)][::-1])
        if mac == '00:00:00:00:00:00':
             return f"{platform.node()}-{platform.system()}-{platform.machine()}".upper()
        return mac.upper()
    except Exception:
        return f"{platform.node()}-{platform.system()}-{platform.machine()}".upper()

def load_private_key():
    """加载私钥用于生成签名 (激活码)。"""
    if not os.path.exists(PRIVATE_KEY_FILE):
        raise FileNotFoundError(f"私钥文件 {PRIVATE_KEY_FILE} 不存在。")
    with open(PRIVATE_KEY_FILE, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=PRIVATE_KEY_PASSWORD, 
            backend=default_backend()
        )
    return private_key

def generate_activation_code(encrypted_machine_id):
    """
    根据加密机器码生成一年有效期的激活码。
    返回: (activation_code, machine_id, expiry_date_str)
    """
    try:
        private_key = load_private_key()
        
        # 1. 解密机器码 (使用私钥解密)
        cipher_text = base64.urlsafe_b64decode(encrypted_machine_id)
        
        machine_id = private_key.decrypt(
            cipher_text,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        ).decode('utf-8')
        
        # 2. 计算过期日期 (1年有效期)
        expiry_date = datetime.date.today() + datetime.timedelta(days=365)
        expiry_date_str = expiry_date.strftime('%Y-%m-%d')
        
        # 3. 构造签名数据 (机器码和有效期)
        data_to_sign = f"{machine_id}|{expiry_date_str}".encode('utf-8')

        # 4. 生成签名
        signature = private_key.sign(
            data_to_sign,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # 5. 构造激活码 (结构化: base64(日期)|base64(签名))
        expiry_b64 = base64.urlsafe_b64encode(expiry_date_str.encode('utf-8')).decode('utf-8')
        signature_b64 = base64.urlsafe_b64encode(signature).decode('utf-8')
        
        activation_code = f"{expiry_b64}|{signature_b64}"
        
        return activation_code, machine_id, expiry_date_str
    
    except InvalidSignature:
        raise Exception("签名无效，私钥或密码可能错误。")
    except Exception as e:
        raise Exception(f"激活码生成失败：{e}")

# ----------------------------------------------------
# Tkinter UI
# ----------------------------------------------------

class LicenseGeneratorApp:
    def __init__(self, master):
        self.master = master
        master.title("软件激活码生成工具")

        # 设置窗口样式和居中
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        window_width = 960
        window_height = 720
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        master.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        master.resizable(False, False) 
        master.configure(bg='#f0f0f0')

        # 样式配置
        font_style = ('Helvetica', 10)
        # 基础样式不包含颜色，避免与后面的 bg/fg 冲突
        button_style = {'font': font_style, 'bd': 0, 'padx': 15, 'pady': 5, 'relief': tk.RAISED}
        
        # 1. 机器码输入区域
        label_frame = tk.Frame(master, bg='#f0f0f0')
        label_frame.pack(pady=(20, 5))

        self.label_machine_code = tk.Label(label_frame, text="【第一步】请输入加密机器码:", font=('Helvetica', 10, 'bold'), bg='#f0f0f0')
        self.label_machine_code.pack(side=tk.LEFT, padx=10)

        # 机器码输入框
        self.text_machine_code = scrolledtext.ScrolledText(master, height=5, width=50, wrap=tk.WORD, font=font_style, bd=2, relief=tk.FLAT)
        self.text_machine_code.pack(pady=5, padx=20)
        
        # 2. 生成按钮
        self.generate_button = tk.Button(master, text="【第二步】生成激活码 (有效期1年)", **button_style, bg='#4CAF50', fg='white', command=self.generate_code)
        self.generate_button.pack(pady=10)
        
        # 3. 激活码结果区域
        self.label_activation_code = tk.Label(master, text="【第三步】生成的激活码:", font=('Helvetica', 10, 'bold'), bg='#f0f0f0')
        self.label_activation_code.pack(pady=(10, 5))
        
        # 激活码显示框
        self.text_activation_code = scrolledtext.ScrolledText(master, height=5, width=50, wrap=tk.WORD, font=font_style, bd=2, relief=tk.FLAT, state=tk.DISABLED)
        self.text_activation_code.pack(pady=5, padx=20)
        self.text_activation_code.insert(tk.END, "请在上方输入机器码，并点击生成按钮...")
        
        # 复制按钮
        self.copy_button = tk.Button(master, text="复制激活码", **button_style, bg='#4CAF50', fg='blue',command=self.copy_code, state=tk.DISABLED)
        self.copy_button.pack(pady=(5, 20))
        
    def generate_code(self):
        encrypted_machine_id = self.text_machine_code.get(1.0, tk.END).strip()
        
        self.text_activation_code.config(state=tk.NORMAL)
        self.text_activation_code.delete(1.0, tk.END)
        self.copy_button.config(state=tk.DISABLED)
        
        if not encrypted_machine_id:
            messagebox.showerror("输入错误", "加密机器码不能为空！")
            self.text_activation_code.insert(tk.END, "生成失败，请输入机器码！")
            self.text_activation_code.config(state=tk.DISABLED)
            return

        try:
            # 调用整合后的核心生成逻辑
            activation_code, machine_id, expiry_date_str = generate_activation_code(encrypted_machine_id)
            
            self.text_activation_code.insert(tk.END, activation_code)
            self.text_activation_code.insert(tk.END, f"\n\n--- 内部详情 (勿发给用户) ---\n原始机器码: {machine_id}\n到期日期: {expiry_date_str}")
            self.copy_button.config(state=tk.NORMAL)
            
            messagebox.showinfo("生成成功", f"激活码已生成，到期日期: {expiry_date_str}")

        except FileNotFoundError as e:
            messagebox.showerror("生成错误 - 密钥文件缺失", str(e))
        except Exception as e:
            error_message = f"激活码生成失败。\n\n错误详情: {e}\n\n请确认:\n1. private_key.pem 文件是否存在。\n2. 密码是否正确。"
            messagebox.showerror("生成错误", error_message)
            
            self.text_activation_code.delete(1.0, tk.END)
            self.text_activation_code.insert(tk.END, "生成失败，请查看弹窗信息！")
            self.copy_button.config(state=tk.DISABLED)
            
        self.text_activation_code.config(state=tk.DISABLED)

    def copy_code(self):
        self.text_activation_code.config(state=tk.NORMAL)
        code_to_copy = self.text_activation_code.get(1.0, "2.0").strip()
        self.text_activation_code.config(state=tk.DISABLED)
        
        if code_to_copy and code_to_copy != "请在上方输入机器码，并点击生成按钮...":
            try:
                self.master.clipboard_clear()
                self.master.clipboard_append(code_to_copy)
                messagebox.showinfo("复制成功", "激活码已复制到剪贴板！")
            except Exception as e:
                 messagebox.showerror("复制失败", f"无法访问剪贴板: {e}")
            
if __name__ == '__main__':
    root = tk.Tk()
    app = LicenseGeneratorApp(root)
    root.mainloop()