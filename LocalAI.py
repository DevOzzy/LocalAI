import tkinter as tk
from tkinter import scrolledtext, filedialog, PanedWindow, messagebox
import ollama
import json
import os
import threading
import subprocess
import sys
import pyttsx3
import speech_recognition as sr
from PIL import Image, ImageTk
import PyPDF2
import sympy
from datetime import datetime

# --- YAPILANDIRMA & GLOBAL DEĞİŞKENLER ---
HISTORY_FILE = "Centauri_AI_chat_history.json"
chat_history = []
document_context = ""
selected_image_path = ""

# Ses Motoru Başlatma (Day 6)
engine = pyttsx3.init()

# --- 1. HAFIZA YÖNETİMİ (Day 4 & 5) ---
def load_history():
    global chat_history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                chat_history = json.load(f)
        except:
            chat_history = []
    else:
        chat_history = []

def save_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(chat_history, f, ensure_ascii=False, indent=4)

# --- 2. ARAÇLAR (TOOLS - Day 10 & 11) ---
def write_code_to_file(filename, content):
    """Yapay zekanın ürettiği kodu dosyaya yazar."""
    try:
        clean_code = content.replace("```python", "").replace("```", "").strip()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(clean_code)
        return f"Dosya oluşturuldu: {filename}"
    except Exception as e:
        return f"Dosya yazma hatası: {str(e)}"

def solve_math(expression, operation="solve"):
    """SymPy ile ileri matematik çözer."""
    try:
        x = sympy.symbols('x')
        expr = sympy.sympify(expression)
        if operation == "solve":
            return str(sympy.solve(expr, x))
        elif operation == "diff":
            return str(sympy.diff(expr, x))
        elif operation == "integrate":
            return str(sympy.integrate(expr, x)) + " + C"
        return "Bilinmeyen işlem."
    except Exception as e:
        return f"Matematik hatası: {str(e)}"

# --- 3. SES & GÖRÜNTÜ İŞLEME (Day 6, 8, 9) ---
def speak_text(text):
    """Metni sese çevirir (TTS)."""
    def run():
        try:
            engine.say(text)
            engine.runAndWait()
        except: pass
    threading.Thread(target=run).start()

def listen_audio():
    """Mikrofonu dinler ve metne çevirir (STT)."""
    recognizer = sr.Recognizer()
    status_label.config(text="Dinleniyor...", fg="red")
    root.update()
    
    def run():
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source)
                audio = recognizer.listen(source, timeout=5)
                text = recognizer.recognize_google(audio, language="tr-TR")
                user_input_field.delete(0, tk.END)
                user_input_field.insert(0, text)
                status_label.config(text="Ses algılandı.", fg="green")
                send_message() # Otomatik gönder
        except Exception as e:
            status_label.config(text=f"Ses hatası: {str(e)}", fg="orange")
    
    threading.Thread(target=run).start()

def upload_image():
    """Resim yükler ve önizler (Vision)."""
    global selected_image_path
    file_path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
    if file_path:
        selected_image_path = file_path
        img = Image.open(file_path)
        img.thumbnail((100, 100))
        img_display = ImageTk.PhotoImage(img)
        lbl_image_preview.config(image=img_display)
        lbl_image_preview.image = img_display
        status_label.config(text="Resim eklendi.", fg="blue")

def upload_pdf():
    """PDF yükler ve metni çeker (RAG - Day 7)."""
    global document_context
    file_path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
    if file_path:
        try:
            reader = PyPDF2.PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            document_context = text
            status_label.config(text="PDF hafızaya alındı.", fg="purple")
        except Exception as e:
            status_label.config(text=f"PDF Hatası: {str(e)}", fg="red")

# --- 4. KOD ÇALIŞTIRMA (Day 12) ---
def execute_editor_code():
    """Sağ paneldeki kodu çalıştırır."""
    code = code_editor.get("1.0", tk.END)
    console_output.config(state=tk.NORMAL)
    console_output.delete("1.0", tk.END)
    console_output.insert(tk.END, ">>> Kod Çalıştırılıyor...\n", "info")
    
    def run():
        try:
            process = subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            
            console_output.insert(tk.END, stdout)
            if stderr:
                console_output.insert(tk.END, f"\nHATA:\n{stderr}", "error")
            console_output.insert(tk.END, "\n>>> İşlem Bitti.", "info")
        except Exception as e:
            console_output.insert(tk.END, f"Sistem Hatası: {str(e)}", "error")
        console_output.config(state=tk.DISABLED)

    threading.Thread(target=run).start()

# --- 5. ANA AI MANTIĞI (Day 3, 10, 11) ---
def get_ai_response(user_input):
    global chat_history, selected_image_path, document_context
    
    # Sistem Promptu (Ajan Davranışı)
    system_prompt = """
    Sen ileri düzey bir AI asistanısın. Python kodlama, matematik ve genel sohbette uzmansın.
    
    Eğer kullanıcı KOD isterse:
    SADECE kodu markdown formatında ver (```python ... ```). Açıklamayı kısa tut.
    
    Eğer kullanıcı MATEMATİK işlemi (türev, integral, denklem) isterse:
    Şu JSON formatında cevap ver: {"tool": "math", "op": "solve/diff/integrate", "expr": "ifade"}
    
    Eğer kullanıcı DOSYA OLUŞTUR derse:
    Şu JSON formatında cevap ver: {"tool": "file", "name": "dosya.py", "content": "kod"}
    
    Normal sohbette yardımsever ve kısa cevaplar ver.
    """
    
    messages = [{'role': 'system', 'content': system_prompt}]
    
    # RAG (Belge) Bağlamı
    if document_context:
        messages.append({'role': 'system', 'content': f"Şu belgeye göre cevapla: {document_context[:2000]}..."})
    
    # Geçmişi ekle
    messages.extend(chat_history[-5:]) # Son 5 mesajı hatırla (Token tasarrufu)
    
    # Yeni Mesaj
    new_msg = {'role': 'user', 'content': user_input}
    
    # Vision (Resim varsa ekle)
    if selected_image_path:
        new_msg['images'] = [selected_image_path]
        model_name = 'llama3.2-vision'
    else:
        model_name = 'llama3.2:1b' # Kodlama için 'codellama' da olabilir
        
    messages.append(new_msg)

    try:
        response = ollama.chat(model=model_name, messages=messages)
        content = response['message']['content']
        
        # Tool Kullanımı Kontrolü (JSON Parsing)
        try:
            if "{" in content and "}" in content:
                json_str = content[content.find("{"):content.rfind("}")+1]
                cmd = json.loads(json_str)
                
                if cmd.get("tool") == "math":
                    return solve_math(cmd["expr"], cmd.get("op", "solve"))
                elif cmd.get("tool") == "file":
                    return write_code_to_file(cmd["name"], cmd["content"])
        except:
            pass # JSON değilse normal metindir

        return content

    except Exception as e:
        return f"AI Hatası: {str(e)}"

# --- 6. GUI (ARAYÜZ) ---
def send_message():
    user_text = user_input_field.get()
    if not user_text and not selected_image_path: return
    
    chat_window.config(state=tk.NORMAL)
    chat_window.insert(tk.END, f"Siz: {user_text}\n", "user")
    user_input_field.delete(0, tk.END)
    chat_window.config(state=tk.DISABLED)
    
    # Hafızaya ekle
    chat_history.append({'role': 'user', 'content': user_text})
    
    def process():
        response = get_ai_response(user_text)
        
        # Hafızaya ekle ve kaydet
        chat_history.append({'role': 'assistant', 'content': response})
        save_history()
        
        # GUI Güncelle
        chat_window.config(state=tk.NORMAL)
        chat_window.insert(tk.END, f"AI: {response}\n\n", "ai")
        chat_window.config(state=tk.DISABLED)
        chat_window.yview(tk.END)
        
        # Sesli Oku (İsteğe bağlı kapatılabilir)
        if len(response) < 200: # Çok uzun kodları okumasın
            speak_text(response)
        
        # Eğer cevap kod içeriyorsa sağ panele aktar
        if "```python" in response:
            try:
                code = response.split("```python")[1].split("```")[0].strip()
                code_editor.delete("1.0", tk.END)
                code_editor.insert(tk.END, code)
            except: pass
            
        # Resmi temizle
        global selected_image_path
        selected_image_path = ""
        lbl_image_preview.config(image="")

    threading.Thread(target=process).start()

# --- GUI BAŞLATMA ---
root = tk.Tk()
root.title("Centauri Offline AI Agent")
root.geometry("1000x700")

# Geçmişi Yükle
load_history()

# Ekranı İkiye Böl (Day 12)
paned = PanedWindow(root, orient=tk.HORIZONTAL)
paned.pack(fill=tk.BOTH, expand=True)

# --- SOL PANEL (CHAT) ---
left_frame = tk.Frame(paned, bg="#f0f0f0")
paned.add(left_frame, minsize=400)

# Toolbar
toolbar = tk.Frame(left_frame)
toolbar.pack(fill=tk.X, pady=5)

btn_mic = tk.Button(toolbar, text="🎤", command=listen_audio, bg="#FF5722", fg="white")
btn_mic.pack(side=tk.LEFT, padx=2)

btn_img = tk.Button(toolbar, text="🖼️", command=upload_image, bg="#2196F3", fg="white")
btn_img.pack(side=tk.LEFT, padx=2)

btn_pdf = tk.Button(toolbar, text="📄", command=upload_pdf, bg="#9C27B0", fg="white")
btn_pdf.pack(side=tk.LEFT, padx=2)

status_label = tk.Label(toolbar, text="Hazır", font=("Arial", 8), fg="gray")
status_label.pack(side=tk.RIGHT, padx=5)

# Chat Area
chat_window = scrolledtext.ScrolledText(left_frame, state=tk.DISABLED, wrap=tk.WORD, font=("Arial", 10))
chat_window.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
chat_window.tag_config("user", foreground="blue")
chat_window.tag_config("ai", foreground="black")

# Resim Önizleme
lbl_image_preview = tk.Label(left_frame)
lbl_image_preview.pack()

# Input
input_frame = tk.Frame(left_frame)
input_frame.pack(fill=tk.X, pady=5)
user_input_field = tk.Entry(input_frame, font=("Arial", 12))
user_input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
user_input_field.bind("<Return>", lambda e: send_message())
tk.Button(input_frame, text="Gönder", command=send_message, bg="#4CAF50", fg="white").pack(side=tk.RIGHT, padx=5)

# --- SAĞ PANEL (KOD EDİTÖRÜ) ---
right_frame = tk.Frame(paned, bg="#1e1e1e")
paned.add(right_frame, minsize=400)

tk.Label(right_frame, text="CANVAS (Python IDE)", bg="#1e1e1e", fg="white").pack(pady=5)

code_editor = scrolledtext.ScrolledText(right_frame, height=20, bg="#2d2d2d", fg="#00ff00", font=("Consolas", 10), insertbackground="white")
code_editor.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
code_editor.insert(tk.END, "# Botun yazdığı kodlar buraya gelecek...\n")

btn_run = tk.Button(right_frame, text="▶ KODU ÇALIŞTIR", command=execute_editor_code, bg="#E91E63", fg="white", font=("Arial", 10, "bold"))
btn_run.pack(pady=5)

tk.Label(right_frame, text="Terminal Çıktısı:", bg="#1e1e1e", fg="white").pack(anchor="w", padx=5)
console_output = scrolledtext.ScrolledText(right_frame, height=10, bg="black", fg="white", font=("Consolas", 9))
console_output.pack(padx=5, pady=5, fill=tk.BOTH)
console_output.tag_config("error", foreground="red")
console_output.tag_config("info", foreground="cyan")

root.mainloop()
