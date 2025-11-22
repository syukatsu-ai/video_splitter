import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
# tkinterdnd2は使用しない
import subprocess
import os
import threading
import math
from datetime import date
import json

class FfmpegSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FFmpeg 動画分割ツール v5 (時間指定対応)")
        self.root.geometry("600x570") # ウィンドウの高さを少し広げます

        self.settings_file = "settings.json"
        self.settings = self.load_settings()
        self.output_path = self.settings.get("output_path", os.path.expanduser("~"))

        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Step 1: ファイル選択
        file_frame = tk.LabelFrame(main_frame, text="Step 1: 分割する動画ファイル")
        file_frame.pack(fill=tk.X, pady=(0, 10))
        self.select_button = tk.Button(file_frame, text="ファイルを選択", command=self.select_file)
        self.select_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.filepath_label = tk.Label(file_frame, text="ファイルが選択されていません", anchor="w", bg="white", relief="sunken")
        self.filepath_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # Step 2: 保存先選択
        output_frame = tk.LabelFrame(main_frame, text="Step 2: 分割ファイルの保存先 (任意)")
        output_frame.pack(fill=tk.X, pady=(0, 10))
        self.output_button = tk.Button(output_frame, text="保存先を選択", command=self.select_output_dir)
        self.output_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.output_label = tk.Label(output_frame, text=self.output_path, anchor="w", bg="white", relief="sunken")
        self.output_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # --- 新機能：Step 2.5: 分割時間の設定 ---
        time_frame = tk.LabelFrame(main_frame, text="Step 2.5: 分割時間の設定 (初期値: 59分30秒)")
        time_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 入力値を保持する変数
        self.minutes_var = tk.StringVar(value="59")
        self.seconds_var = tk.StringVar(value="30")
        
        # 分の入力
        min_label = tk.Label(time_frame, text="分:")
        min_label.pack(side=tk.LEFT, padx=(5, 0))
        self.min_entry = tk.Entry(time_frame, textvariable=self.minutes_var, width=5)
        self.min_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        # 秒の入力
        sec_label = tk.Label(time_frame, text="秒:")
        sec_label.pack(side=tk.LEFT, padx=(5, 0))
        self.sec_entry = tk.Entry(time_frame, textvariable=self.seconds_var, width=5)
        self.sec_entry.pack(side=tk.LEFT, padx=(5, 5))
        # --- ここまで新機能 ---
        
        # Step 3: 実行
        self.run_button = tk.Button(main_frame, text="Step 3: 分割を実行", command=self.start_split_thread, state=tk.DISABLED, pady=5)
        self.run_button.pack(pady=(5, 10), fill=tk.X)

        # ログ表示
        log_label = tk.Label(main_frame, text="処理ログ:")
        log_label.pack(anchor="w")
        self.log_area = scrolledtext.ScrolledText(main_frame, height=10, state=tk.DISABLED)
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except IOError:
            self.log("エラー: 設定ファイルの保存に失敗しました。")

    def select_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")])
        if filepath:
            self.process_filepath(filepath)
            
    def process_filepath(self, filepath):
        if not os.path.isfile(filepath):
            self.log(f"エラー: 無効なファイルパスです -> {filepath}")
            return
        self.input_path = filepath
        self.filepath_label.config(text=os.path.basename(filepath))
        self.run_button.config(state=tk.NORMAL)
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state=tk.DISABLED)
        self.log(f"ファイル選択: {self.input_path}")

    def select_output_dir(self):
        dir_path = filedialog.askdirectory(initialdir=self.output_path)
        if dir_path:
            self.output_path = dir_path
            self.output_label.config(text=dir_path)
            self.log(f"保存先を変更: {self.output_path}")
            self.settings["output_path"] = self.output_path
            self.save_settings()

    def log(self, message):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def set_ui_state(self, is_running):
        state = tk.DISABLED if is_running else tk.NORMAL
        self.select_button.config(state=state)
        self.output_button.config(state=state)
        self.run_button.config(state=state)
        self.min_entry.config(state=state) # 入力欄も無効化/有効化
        self.sec_entry.config(state=state)

    def start_split_thread(self):
        if not self.input_path:
            messagebox.showwarning("警告", "動画ファイルが選択されていません。")
            return
        
        # --- 変更点：入力された時間（分・秒）を読み取る ---
        try:
            minutes = int(self.minutes_var.get())
            seconds = int(self.seconds_var.get())
            total_duration = (minutes * 60) + seconds
            
            if total_duration <= 0:
                messagebox.showerror("入力エラー", "分割時間は0より大きい値にしてください。")
                return
        except ValueError:
            messagebox.showerror("入力エラー", "分と秒には有効な数値を入力してください。")
            return
        # --- 変更点ここまで ---

        self.set_ui_state(True)
        # スレッドに計算した分割時間(total_duration)を渡す
        thread = threading.Thread(target=self.split_video_process, args=(total_duration,), daemon=True)
        thread.start()

    # def split_video_process(self, split_duration=3570): # ← 以前のハードコードされた値
    def split_video_process(self, split_duration):      # ← 渡された値を使うよう変更
        """動画分割のコアロジック"""
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            video_basename = os.path.splitext(os.path.basename(self.input_path))[0]
            output_folder_name = f"{today_str}_{video_basename}"
            final_output_dir = os.path.join(self.output_path, output_folder_name)
            
            self.log(f"保存先フォルダを作成します: {final_output_dir}")
            os.makedirs(final_output_dir, exist_ok=True)
            
            self.log("動画の長さを取得中...")
            probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", self.input_path]
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            duration = float(result.stdout)
            
            # 渡されたsplit_durationを使用する
            self.log(f"分割時間: {split_duration} 秒 ({split_duration/60:.2f} 分) で処理します。")
            
            base_name, ext = os.path.splitext(os.path.basename(self.input_path))
            num_parts = math.ceil(duration / split_duration)
            self.log(f"{num_parts}個のファイルに分割します...")

            for i in range(num_parts):
                start_time = i * split_duration
                output_filename = f"{base_name}_part_{i+1}{ext}"
                full_output_path = os.path.join(final_output_dir, output_filename)
                
                self.log(f"\n--- パート {i+1}/{num_parts} を作成中 ---")
                
                # -t オプションに渡された split_duration を使用する
                split_cmd = ["ffmpeg", "-i", self.input_path, "-ss", str(start_time), "-t", str(split_duration), "-c", "copy", "-y", full_output_path]
                
                process = subprocess.run(split_cmd, capture_output=True, text=True, encoding='utf-8')

                if process.returncode == 0:
                    self.log(f"-> 成功: '{full_output_path}' を保存しました。")
                else:
                    raise Exception(f"FFmpegがエラーを返しました:\n{process.stderr}")

            self.log("\n✅ すべての処理が完了しました。")
            messagebox.showinfo("完了", f"動画の分割が完了しました。\n保存先: {final_output_dir}")

        except FileNotFoundError:
            self.log("致命的なエラー: FFmpegが見つかりません。")
            messagebox.showerror("エラー", "FFmpegがインストールされていないか、PATHが通っていません。")
        except Exception as e:
            self.log(f"エラーが発生しました: {e}")
            messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n{e}")
        finally:
            self.set_ui_state(False)

if __name__ == '__main__':
    root = tk.Tk()
    app = FfmpegSplitterApp(root)
    root.mainloop()