import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pypdf
import re
import json
import os
import unicodedata

class RSVPReader:
    def __init__(self, root):
        self.root = root
        self.root.title("RSVP Reader")
        self.root.geometry("800x400")
        self.root.configure(bg='black')

        self.base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(self.base_path, "icon.png")

        try:
            if os.path.exists("icon.png"):
                icon_image = tk.PhotoImage(file="icon.png")
                self.root.iconphoto(False, icon_image)
        except Exception as e:
            print(f"Warning: Could not load icon.png: {e}")

        self.wpm = 350
        self.is_playing = False
        self.words = []
        self.full_raw_text = "" # Store original text for visualization
        self.current_index = 0
        self.font_face = "Consolas" 
        self.font_size = 40
        
        self.bg_color = "#000000"
        self.text_color = "#e0e0e0" 
        self.highlight_color = "#ff3333" 
        self.crosshair_color = "#cc0000"

        self.english_dict = None
        self.load_dictionary()

        # Common short words/stop words
        self.safe_short_words = {
            "a", "an", "as", "at", "am", "be", "by", "do", "go", "he", "hi", "if", "in", "is", "it", 
            "me", "my", "no", "of", "on", "or", "ok", "so", "to", "up", "us", "we", "i",
            "the", "and", "but", "for", "not", "yes", "can", "did", "put", "say", "she", "too", 
            "use", "who", "why", "you", "are", "all", "any", "day", "get", "has", "him", "his", 
            "how", "man", "new", "now", "old", "one", "out", "own", "see", "two", "way", "our",
            "that", "this", "these", "those", "with", "from", "have"
        }

        self._setup_ui()
        self._draw_crosshairs()

    def load_dictionary(self):
        dict_path = os.path.join(self.base_path, 'dictionary.json')
        try:
            if os.path.exists(dict_path):
                with open(dict_path, 'r', encoding='utf-8') as f:
                    self.english_dict = json.load(f)
                print("Dictionary loaded. Smart citation filtering enabled.")
            else:
                print("Warning: 'dictionary.json' not found. Reverting to basic regex filtering.")
        except Exception as e:
            print(f"Error loading dictionary: {e}")
            self.english_dict = None

    def _setup_ui(self):
        control_frame = tk.Frame(self.root, bg='#1a1a1a')
        control_frame.pack(side=tk.TOP, fill=tk.X)
        
        btn_style = {"bg": "#333", "fg": "white", "relief": "flat", "padx": 10}

        tk.Button(control_frame, text="Load PDF", command=self.load_pdf, **btn_style).pack(side=tk.LEFT, padx=5, pady=5)
        self.btn_toggle = tk.Button(control_frame, text="Start", command=self.toggle_reading, **btn_style)
        self.btn_toggle.pack(side=tk.LEFT, padx=5, pady=5)

        tk.Label(control_frame, text="WPM:", bg="#1a1a1a", fg="white").pack(side=tk.LEFT, padx=5)
        self.wpm_entry = tk.Entry(control_frame, width=5)
        self.wpm_entry.insert(0, str(self.wpm))
        self.wpm_entry.pack(side=tk.LEFT)
        tk.Button(control_frame, text="Set", command=self.update_wpm, **btn_style).pack(side=tk.LEFT, padx=2)
        
        tk.Button(control_frame, text="Visualize Text", command=self.visualize_sanitization, **btn_style).pack(side=tk.LEFT, padx=15, pady=5)

        if not self.english_dict:
            status_text = "Dictionary Missing"
            fg_color = "#ff4444"
            tk.Label(control_frame, text=status_text, bg="#1a1a1a", fg=fg_color, font=("Arial", 8)).pack(side=tk.RIGHT, padx=10)

        self.canvas = tk.Canvas(self.root, bg=self.bg_color, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self._draw_crosshairs())

    def _draw_crosshairs(self):
        self.canvas.delete("ui_overlay")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx, cy = w / 2, h / 2

        self.canvas.create_line(cx, cy - 80, cx, cy - 35, fill=self.crosshair_color, width=2, tags="ui_overlay")
        self.canvas.create_line(cx, cy + 35, cx, cy + 80, fill=self.crosshair_color, width=2, tags="ui_overlay")

        self.canvas.create_line(cx - 10, cy - 65, cx + 10, cy - 65, fill=self.crosshair_color, width=2, tags="ui_overlay")
        self.canvas.create_line(cx - 10, cy + 65, cx + 10, cy + 65, fill=self.crosshair_color, width=2, tags="ui_overlay")

    def clean_scientific_metadata(self, text):

        match = re.search(r'\n\s*(?:Abstract|ABSTRACT|Introduction|INTRODUCTION)', text[:5000])
        if match:
            text = text[match.start():]
        
        tail_match = re.search(r'(?m)^\s*(?:References|REFERENCES|Bibliography|BIBLIOGRAPHY|Appendix|APPENDIX|Appendices|APPENDICES)(?:\s+[A-Z0-9]*)?\s*$', text)
        if tail_match:
            text = text[:tail_match.start()]
        
        # Explicitly remove arXiv and Conference headers/footers
        text = re.sub(r'(?i)arXiv:[\d\.]+(v\d+)?\s*\[.*?\]', '', text)
        text = re.sub(r'(?i)Published as a conference paper at.*', '', text)

        text = re.sub(r'\{?[\w\.,\s-]+\}?@[\w\.-]+\.\w+', '', text)
        affiliation_keywords = r'(University|Institute|Department|Laboratory|School of|Center for|Inc\.|Ltd\.)'
        text = re.sub(r'(?m)^\s*[\d\*,†‡§]*\s*.*' + affiliation_keywords + r'.*$', '', text)
        text = re.sub(r'(?i).*(submitted to|accepted by|preprint|conference|journal).*', '', text)
        
        return text

    def _is_english_content(self, text_chunk):
        clean_chunk = re.sub(r'[^\w\s]', '', text_chunk)
        words = clean_chunk.split()
        
        if not words: 
            return False
        
        english_count = sum(1 for word in words if self.english_dict.get(word.lower()) is not None)
        
        # Calculate ratio
        ratio = english_count / len(words)
        
        if len(words) > 0 and ratio >= 0.5:
            return True
        else:
            return False

    def _is_line_useful(self, line):
        stripped_line = line.strip()
        if not stripped_line:
            return False

        # Real sentences are mostly alphabetic. Math/Diagrams are symbol-heavy
        # "x(1:H)" -> x, H (2 alpha) vs (, :, ), 1 (4 symbols/digits). 33% alpha, gets rejected
        alpha_count = sum(c.isalpha() or c.isspace() for c in stripped_line)
        if alpha_count / len(stripped_line) < 0.70:
            return False

        tokens = stripped_line.split()
        if not tokens: return False

        valid_count = 0
        safe_word_found = False
        
        for t in tokens:
            clean_t = t.strip(".,;:()[]{}'\"“”‘’") 
            if not clean_t: continue
            
            # Reject internal caps (yNon), mixed numbers (S4), single uppercase (A, B)
            if any(c.isdigit() for c in clean_t): continue
            # Allow "I" and "A" (start of sentence), reject other single upper letters
            if len(clean_t) == 1 and clean_t.isupper() and clean_t not in ["I", "A"]: continue
            # Reject camelCase (yNon) - must be all lower, all upper, or title case
            if not (clean_t.islower() or clean_t.isupper() or clean_t.istitle()): continue

            lower_t = clean_t.lower()
            
            if lower_t in self.safe_short_words:
                safe_word_found = True
                valid_count += 1
            elif (self.english_dict and self.english_dict.get(lower_t)) or len(clean_t) > 3:
                valid_count += 1
        
        # Sentence vs Label Heuristic
        # Diagram labels ("Parallel scan", "Layer input") are short and lack "safe" function words.
        # Sentences usually have function words ("The", "is") OR end in punctuation.
        if len(tokens) < 7:
            ends_in_punct = stripped_line[-1] in ".!?"
            if not safe_word_found and not ends_in_punct:
                return False

        # Final ratio chack to filter gibberish lines
        if len(tokens) > 0:
            ratio = valid_count / len(tokens)
            return ratio >= 0.6
        
        return False

    def sanitize_text(self, raw_text):
        if not raw_text:
            return []

        # Clean Headers/Footers first
        text = self.clean_scientific_metadata(raw_text)
        
        # Line-by-Line Filtering (Strict)
        lines = text.splitlines()
        kept_lines = []
        for line in lines:
            if self._is_line_useful(line):
                kept_lines.append(line)
        
        text = " ".join(kept_lines)

        # Standard Cleanup on the remaining valid text
        if self.english_dict:
            def bracket_callback(match):
                content = match.group() 
                if self._is_english_content(content):
                    return content
                else:
                    return ""
                
            text = re.sub(r'\([^\)]+\)|\[[^\]]+\]', bracket_callback, text)
        else:
            text = re.sub(r'\[\s*[\d,\s-]+\s*\]', '', text)
            text = re.sub(r'\([A-Z][a-zA-Z\s.,&]+,?\s\d{4}[a-z]?\)', '', text)

        # Remove URLs/DOIs
        text = re.sub(r'http[s]?://\S+', '', text)
        text = re.sub(r'doi:\S+', '', text)

        # Remove math
        math_symbols = r'[=+\-*/<>^~∫∑∏√∞∂∇≈≠≤≥\u2010-\u2015\u2212]'
        text = re.sub(math_symbols, ' ', text)

        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)

        raw_words = text.split()
        clean_words = []
        
        for w in raw_words:
            stripped = w.strip(".,;:()[]{}'\"“”‘’")
            if not stripped: continue
            
            # Filter internal caps/mixed numbers again just in case
            if any(c.isdigit() for c in stripped): continue
            if not (stripped.islower() or stripped.isupper() or stripped.istitle()): continue
            
            # Remove purely single characters that aren't words (keep 'a', 'I', 'A')
            if len(stripped) == 1 and stripped not in ['a', 'A', 'I']:
                continue
                
            if "_" in w or "\\" in w:
                continue

            clean_words.append(w)

        return clean_words

    def load_pdf(self):
        filename = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not filename:
            return

        try:
            reader = pypdf.PdfReader(filename)
            full_text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    full_text += extracted + " "
            
            self.full_raw_text = full_text # Store for visualization
            self.words = self.sanitize_text(full_text)
            self.current_index = 0
            messagebox.showinfo("Success", f"Cleaned & Loaded {len(self.words)} words.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not read PDF: {e}")

    def get_sanitization_mask(self, text):
        """Creates a boolean mask for the raw text matching regex removals."""
        mask = [True] * len(text)
        
        def remove(start, end):
            s = max(0, start)
            e = min(len(mask), end)
            for i in range(s, e):
                mask[i] = False

        # Metadata
        match = re.search(r'\n\s*(?:Abstract|ABSTRACT|Introduction|INTRODUCTION)', text[:5000])
        if match:
            remove(0, match.start()) 

        # References / Bibliography / Appendix
        # Search for lines containing specific headers and cut everything after them.
        tail_match = re.search(r'(?m)^\s*(?:References|REFERENCES|Bibliography|BIBLIOGRAPHY|Appendix|APPENDIX|Appendices|APPENDICES)(?:\s+[A-Z0-9]*)?\s*$', text)
        if tail_match:
             remove(tail_match.start(), len(text))

        # Affiliations
        affiliation_keywords = r'(University|Institute|Department|Laboratory|School of|Center for|Inc\.|Ltd\.)'
        for m in re.finditer(r'(?m)^\s*[\d\*,†‡§]*\s*.*' + affiliation_keywords + r'.*$', text):
             remove(m.start(), m.end())
        
        # Submission Status / arXiv / Conference
        for m in re.finditer(r'(?i).*(submitted to|accepted by|preprint|conference|journal).*', text):
             remove(m.start(), m.end())
        for m in re.finditer(r'(?i)arXiv:[\d\.]+(v\d+)?\s*\[.*?\]', text):
             remove(m.start(), m.end())
        for m in re.finditer(r'(?i)Published as a conference paper at.*', text):
             remove(m.start(), m.end())

        # Emails
        for m in re.finditer(r'\{?[\w\.,\s-]+\}?@[\w\.-]+\.\w+', text):
             remove(m.start(), m.end())

        # Citations / Brackets
        if self.english_dict:
            for m in re.finditer(r'\([^\)]+\)|\[[^\]]+\]', text):
                if not self._is_english_content(m.group()):
                    remove(m.start(), m.end())
        else:
            for m in re.finditer(r'\[\s*[\d,\s-]+\s*\]', text):
                remove(m.start(), m.end())
            for m in re.finditer(r'\([A-Z][a-zA-Z\s.,&]+,?\s\d{4}[a-z]?\)', text):
                remove(m.start(), m.end())

        # URLs/DOIs
        for m in re.finditer(r'http[s]?://\S+', text): remove(m.start(), m.end())
        for m in re.finditer(r'doi:\S+', text): remove(m.start(), m.end())
        
        # Hyphenation Fix (The hyphen and newline chars are removed)
        for m in re.finditer(r'-\s*\n', text):
            remove(m.start(), m.end())
            
        # Math
        math_symbols = r'[=+\-*/<>^~∫∑∏√∞∂∇≈≠≤≥\u2010-\u2015\u2212]'
        for m in re.finditer(math_symbols, text):
            remove(m.start(), m.end())

        return mask

    def get_line_validity_mask(self, text):
        mask = [True] * len(text)
        
        for m in re.finditer(r'^.*$', text, re.MULTILINE):
            line = m.group()
            if not self._is_line_useful(line):
                for i in range(m.start(), m.end()):
                    mask[i] = False
        
        return mask

    def visualize_sanitization(self):
        if not self.full_raw_text:
            messagebox.showinfo("Info", "Load a PDF first.")
            return

        vis_window = tk.Toplevel(self.root)
        vis_window.title("Text Visualizer")
        vis_window.geometry("900x600")
        vis_window.configure(bg="#1e1e1e")

        try:
            if os.path.exists("icon.png"):
                icon_image = tk.PhotoImage(file="icon.png")
                vis_window.iconphoto(False, icon_image)
        except:
            pass

        text_area = scrolledtext.ScrolledText(vis_window, wrap=tk.WORD, font=("Consolas", 11), bg="#1e1e1e")
        text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_area.tag_config("kept", foreground="#e0e0e0")
        text_area.tag_config("removed", foreground="#ff4444", background="#330000")

        regex_mask = self.get_sanitization_mask(self.full_raw_text)
        line_mask = self.get_line_validity_mask(self.full_raw_text)
        
        final_mask = [r and l for r, l in zip(regex_mask, line_mask)]
        
        if not final_mask:
            return

        # Render
        current_status = final_mask[0]
        start_idx = 0
        
        for i, status in enumerate(final_mask):
             if status != current_status:
                 tag = "kept" if current_status else "removed"
                 text_area.insert(tk.END, self.full_raw_text[start_idx:i], tag)
                 start_idx = i
                 current_status = status
        
        tag = "kept" if current_status else "removed"
        text_area.insert(tk.END, self.full_raw_text[start_idx:], tag)

        text_area.configure(state='disabled')

    def get_pivot_index(self, word):
        length = len(word)
        if length == 1: return 0
        if length in [2, 3, 4, 5]: return 1
        return (length // 2) - 1

    def draw_word(self, word):
        self.canvas.delete("text")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx, cy = w / 2, h / 2

        pivot_idx = self.get_pivot_index(word)
        
        left_part = word[:pivot_idx]
        pivot_char = word[pivot_idx]
        right_part = word[pivot_idx+1:]

        # Draw Pivot
        self.canvas.create_text(cx, cy, text=pivot_char, 
                                font=(self.font_face, self.font_size, "bold"), 
                                fill=self.highlight_color, anchor="center", tags="text")

        # Draw Left Part (East anchored to center)
        self.canvas.create_text(cx - (self.font_size*0.35), cy, text=left_part, 
                                font=(self.font_face, self.font_size), 
                                fill=self.text_color, anchor="e", tags="text")

        # Draw Right Part (West anchored to center)
        self.canvas.create_text(cx + (self.font_size*0.35), cy, text=right_part, 
                                font=(self.font_face, self.font_size), 
                                fill=self.text_color, anchor="w", tags="text")

    def update_wpm(self):
        try:
            self.wpm = int(self.wpm_entry.get())
        except ValueError:
            pass

    def toggle_reading(self):
        if not self.words:
            return
        self.is_playing = not self.is_playing
        self.btn_toggle.config(text="Pause" if self.is_playing else "Resume")
        if self.is_playing:
            self.run_rsvp_loop()

    def run_rsvp_loop(self):
        if not self.is_playing or self.current_index >= len(self.words):
            self.is_playing = False
            self.btn_toggle.config(text="Start")
            return

        word = self.words[self.current_index]
        self.draw_word(word)
        
        base_delay = 60000 / self.wpm 
        delay_mult = 1.0
        
        if word.endswith('.'): delay_mult = 2.2 
        elif word.endswith(','): delay_mult = 1.5
        elif word.endswith(';'): delay_mult = 1.5
        elif len(word) > 10: delay_mult = 1.4 
        
        self.current_index += 1
        self.root.after(int(base_delay * delay_mult), self.run_rsvp_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = RSVPReader(root)
    root.mainloop()