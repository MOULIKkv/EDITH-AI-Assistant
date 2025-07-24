import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.utils import get_color_from_hex

import google.generativeai as genai
import os
import pyttsx3
import speech_recognition as sr
import threading

# --- Modern Gen Z Color Palette ---
BACKGROUND_COLOR = get_color_from_hex('#121212')
PRIMARY_COLOR = get_color_from_hex('#1E1E1E')
ACCENT_COLOR = get_color_from_hex('#BB86FC')
TEXT_COLOR = get_color_from_hex('#E0E0E0')

Window.clearcolor = BACKGROUND_COLOR


class ModernApp(App):
    def build(self):
        # --- FONT ---
        self.font = 'Poppins-Regular.ttf'

        # --- Words to stop the AI from talking ---
        self.stop_words = ['stop', 'shut up', 'be quiet', 'cancel', 'hush']

        # --- AI & TTS Setup ---
        self.tts_engine = pyttsx3.init()
        try:
            # Your API Key Here
            os.environ['GOOGLE_API_KEY'] = "AIzaSyBr8pXAbrAcGhThnE1TmOSz5D6Amq6S0G8"
            genai.configure(api_key=os.environ['GOOGLE_API_KEY'])
            safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in
                               ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                                "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
            self.model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
            self.chat = self.model.start_chat(history=[])
            print("Gemini model initialized successfully.")
        except Exception as e:
            print(f"Error initializing Gemini: {e}")
            self.chat = None
        main_layout = BoxLayout(orientation='vertical', spacing=20, padding=[30, 40, 30, 40])
        profile_image = Image(source='profile.png', size_hint=(None, None), size=(120, 120), allow_stretch=True, pos_hint={'center_x': 0.5})
        main_layout.add_widget(profile_image)
        main_layout.add_widget(Label(size_hint_y=None, height=10))

        results_view = ScrollView(size_hint=(1, 1), bar_width=10, bar_color=ACCENT_COLOR)
        self.results_label = Label(
            text="Hey! I'm EDITH.\nAsk me anything.",
            color=TEXT_COLOR, font_size='16sp', font_name=self.font,
            size_hint_y=None, text_size=(main_layout.width * 0.9, None),
            halign='center', valign='top'
        )
        self.results_label.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        results_view.add_widget(self.results_label)
        main_layout.add_widget(results_view)

        input_bar_layout = BoxLayout(size_hint_y=None, height=60, spacing=10)
        with input_bar_layout.canvas.before:
            Color(rgba=PRIMARY_COLOR)
            self.input_rect = RoundedRectangle(pos=input_bar_layout.pos, size=input_bar_layout.size, radius=[30])
        input_bar_layout.bind(pos=self.update_canvas, size=self.update_canvas)

        self.text_input = TextInput(
            hint_text="Message EDITH...", font_name=self.font,
            background_color=(0, 0, 0, 0), foreground_color=TEXT_COLOR,
            cursor_color=ACCENT_COLOR, multiline=False,
            size_hint_x=0.8, padding=[20, 20, 0, 20]
        )
        self.text_input.bind(on_text_validate=self.start_ai_thread)

        voice_btn = Button(
            text="🎙️", font_size='24sp', size_hint=(None, None), size=(60, 60),
            background_color=(0, 0, 0, 0), on_press=self.start_voice_thread
        )

        input_bar_layout.add_widget(self.text_input)
        input_bar_layout.add_widget(voice_btn)
        main_layout.add_widget(input_bar_layout)

        return main_layout

    def update_canvas(self, instance, value):
        self.input_rect.pos = instance.pos
        self.input_rect.size = instance.size

    # --- CHANGED: Simplified the speak method ---
    def speak(self, text):
        threading.Thread(target=self._execute_tts, args=(text,)).start()

    def _execute_tts(self, text):
        try:
            self.tts_engine.stop() # Interrupt any previous speech
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            print(f"TTS Error: {e}")

    def start_voice_thread(self, instance):
        # --- NEW: Stop speech immediately when voice input starts ---
        self.tts_engine.stop()
        threading.Thread(target=self.voice_input).start()

    def voice_input(self):
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            Clock.schedule_once(lambda dt: self.update_results("Listening..."))
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                query = recognizer.recognize_google(audio)
                Clock.schedule_once(lambda dt: self.set_query(query))
                Clock.schedule_once(lambda dt: self.start_ai_thread(None))
            except Exception:
                fallback_text = "Sorry, I didn't catch that. Please try again."
                self.update_results(fallback_text)
                self.speak(fallback_text)

    def set_query(self, query):
        self.text_input.text = query

    # --- CHANGED: This function now handles interruption better ---
    def start_ai_thread(self, instance):
        query = self.text_input.text.lower().strip()

        # Instantly stop any ongoing speech
        self.tts_engine.stop()

        # Check for stop words
        if query in self.stop_words:
            self.text_input.text = ""
            self.update_results("Speech cancelled.")
            return

        if query:
            self.text_input.text = ""
            self.update_results("✨ Thinking...")
            threading.Thread(target=self.get_ai_response, args=(query,)).start()

    def get_ai_response(self, query):
        if not self.chat:
            error_message = "AI brain not available. Please check your API key."
            self.update_results(error_message)
            self.speak(error_message)
            return

        full_response_text = ""
        try:
            response_stream = self.chat.send_message(query, stream=True)
            for chunk in response_stream:
                full_response_text += chunk.text
                Clock.schedule_once(lambda dt, text=full_response_text: self.update_results(text))

            if not full_response_text.strip():
                fallback_message = "I can't respond to that. Try another question! 😊"
                self.update_results(fallback_message)
                self.speak(fallback_message)
            else:
                self.speak(full_response_text)

        except Exception as e:
            error_message = f"Oops! An error occurred. Please check your connection or API key."
            self.update_results(error_message)
            self.speak(error_message)

    def update_results(self, text):
        Clock.schedule_once(lambda dt: setattr(self.results_label, 'text', text))


if __name__ == '__main__':
    ModernApp().run()