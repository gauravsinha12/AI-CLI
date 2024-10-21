import tkinter as tk
from tkinter import scrolledtext, font
import subprocess
import os
import glob
import threading
import groq
import ast
import json
import random

class CMDLikeApp:
    def __init__(self, master):
        self.master = master
        master.title("CMD-like Application")
        master.configure(bg='#1E1E1E')

        master.geometry("900x700")

        self.output_font = font.Font(family="Consolas", size=12)
        self.input_font = font.Font(family="Consolas", size=14, weight="bold")

        self.output_area = scrolledtext.ScrolledText(master, wrap=tk.WORD, bg="#1E1E1E", fg="#00FF00", 
                                                     insertbackground="#00FF00", font=self.output_font)
        self.output_area.pack(expand=True, fill='both', padx=10, pady=10)
        self.output_area.config(state='disabled')

        self.input_frame = tk.Frame(master, bg="#1E1E1E")
        self.input_frame.pack(fill='x', padx=10, pady=5)

        self.prompt_label = tk.Label(self.input_frame, text=f"{os.getcwd()}>", bg="#1E1E1E", fg="#FFD700", 
                                     font=self.input_font)
        self.prompt_label.pack(side='left')

        self.input_entry = tk.Entry(self.input_frame, bg="#2E2E2E", fg="#FFFFFF", insertbackground="#FFFFFF", 
                                    font=self.input_font)
        self.input_entry.pack(side='left', expand=True, fill='x', padx=(5, 0))
        self.input_entry.bind("<Return>", self.process_command)
        self.input_entry.bind("<Tab>", self.auto_complete)
        self.input_entry.bind("<Up>", self.previous_command)
        self.input_entry.bind("<Down>", self.next_command)
        
        self.ai_robot_ascii = """
     ,     ,
    (\____/)
     (_oo_)
       (O)
     __||__    \)
  []/______\[] /
  / \______/ \/
 /    
(\  
        """

        self.command_history = []
        self.history_index = -1

        self.groq_suggestions = []
        self.suggestion_index = 0

        self.groq_client = groq.Groq(api_key="Groq Key")

        self.context_file = "session_context.json"
        self.load_context()

        self.append_output("Welcome to the CLAI.\n", "#00FFFF")
        self.append_output("Type a command and press Enter to execute.\n\n", "#00FFFF")

    def append_output(self, text, color="#00FF00"):
        colors = f"#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}"
        if color is None:
            color = random.choice(colors)
        self.output_area.config(state='normal')
        self.output_area.insert(tk.END, text, color)
        self.output_area.see(tk.END)
        self.output_area.config(state='disabled')

    def update_prompt(self):
        self.prompt_label.config(text=f"{os.getcwd()}>")

    def process_command(self, event):
        command = self.input_entry.get()
        self.append_output(f"{os.getcwd()}>{command}\n")

        if command.strip():
            self.command_history.append(command)
            self.history_index = -1
            self.update_context("last_user_input", command)

        self.input_entry.delete(0, tk.END)

        if command.lower().startswith("cd "):
            self.change_directory(command[3:])
        elif command.lower() == "exit":
            self.save_context()
            self.master.quit()
        elif command.lower() == "cls":
            self.clear_screen()
        elif command.lower() == "i can":
            self.groq_suggestions = []
            self.suggestion_index = 0
        else:
            threading.Thread(target=self.execute_command, args=(command,)).start()

    def clear_screen(self):
        self.output_area.config(state='normal')
        self.output_area.delete(1.0, tk.END)
        self.output_area.config(state='disabled')

    def change_directory(self, path):
        try:
            os.chdir(path)
            self.update_prompt()
        except FileNotFoundError:
            self.append_output(f"The system cannot find the path specified: {path}\n")
        except Exception as e:
            self.append_output(f"Error changing directory: {e}\n")


    def execute_command(self, command):
        try:
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            self.append_output(result.stdout)
            
            if self.groq_suggestions and command == self.groq_suggestions[self.suggestion_index - 1]:
                self.set_next_suggestion()
            else:
                self.groq_suggestions = []
                self.suggestion_index = 0
        except subprocess.CalledProcessError as e:
            self.append_output(f"Error: {e}\n")
            self.retry_with_groq(command, str(e))

    def retry_with_groq(self, command, error_message):
        groq_suggestion = self.generate_command(command, error_message)
        if groq_suggestion:
            self.append_output(f"Suggested fix for '{command}':\n", "#00FFFF")
            self.append_output(f"{groq_suggestion}\n", "#FFFF00")  # Show the suggestion
            self.input_entry.delete(0, tk.END)  # Put the suggestion in the input field for the user
            self.input_entry.insert(0, groq_suggestion)  # Allow user to edit it if needed
        else:
            self.append_output(f"No suggestion available for '{command}'.\n", "#FF0000")


    def generate_command(self, user_input, error_message):
        try:
            prompt = f"""
            You are a helpful bot which reads the inputs given by the user in a CMD, and the user is either asking for commands to perform some task or writing an incorrect command. 
            We need to first identify what the user wants or needs. 

            Let's take some examples:

            The example below shows how to handle a user's request or question:

            input :- "I want to commit a folder which is in D drive and the folder name is sql."
            output :- 1. "D:" 
            2."cd sql"
            3."git init" 
            4."git add ." 
            5."git commit -m \\"Initial commit of sql folder\\""
            6."git remote add origin <remote_repo_URL>", "git push -u origin master"

            The example below shows how to handle a mistyped or syntactically incorrect command:

            input :- "conpat /c sample_file.txt"
            output :- 1."compact /c sample_file.txt"

            Based on this, you must first identify if the input is a request, question, or a syntax error, and then provide the output accordingly. 

            Mandatory rules for your response:
            1. Your response should only contain commands in a list which has non-repeated and step-wise commands.
            2. You must not provide any extra text in your response.

            This is the user input :- {user_input}
            This is the error message :- {error_message}

            For your context, this is the current directory path, and generally treat every PC as having simple drive names (like C:, D:, E:, F:): {os.getcwd()}

            Previous context: {self.context}
            """

            chat_completion = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
            )
            groq_output = chat_completion.choices[0].message.content.strip()
            self.append_output(self.ai_robot_ascii)
            self.append_output("CLAI Suggestion  :")
            self.append_output(f"{groq_output}\n")
            self.update_context("last_groq_output", groq_output)
            return groq_output

        except Exception as e:
            return f"Error communicating with Groq API: {e}"

    def process_groq_suggestion(self, suggestion):
        try:
            self.groq_suggestions = ast.literal_eval(suggestion)
            self.suggestion_index = 0
            self.set_next_suggestion()
        except (SyntaxError, ValueError):
            self.append_output(f"Error processing CLAI suggestionggestion: {suggestion}\n")

    def set_next_suggestion(self):
        if self.suggestion_index < len(self.groq_suggestions):
            next_command = self.groq_suggestions[self.suggestion_index]
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, next_command)  # Let user modify it if necessary
            self.suggestion_index += 1
        else:
            self.groq_suggestions = []
            self.suggestion_index = 0


    def auto_complete(self, event):
        current_input = self.input_entry.get()

        if current_input.lower().startswith("cd "):
            path = current_input[3:]
            if not path:
                return "break"

            possible_paths = glob.glob(os.path.join(os.getcwd(), path + "*"))
            if possible_paths:
                completion = os.path.basename(possible_paths[0])
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, f"cd {completion}")

        return "break"

    def previous_command(self, event):
        if self.command_history:
            if self.history_index == -1:
                self.history_index = len(self.command_history) - 1
            elif self.history_index > 0:
                self.history_index -= 1
            
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, self.command_history[self.history_index])

        return "break"

    def next_command(self, event):
        if self.command_history:
            if self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, self.command_history[self.history_index])
            elif self.history_index == len(self.command_history) - 1:
                self.history_index = -1
                self.input_entry.delete(0, tk.END)

        return "break"

    def load_context(self):
        try:
            with open(self.context_file, 'r') as f:
                self.context = json.load(f)
        except FileNotFoundError:
            self.context = {"last_user_input": "", "last_groq_output": ""}

    def save_context(self):
        with open(self.context_file, 'w') as f:
            json.dump(self.context, f)

    def update_context(self, key, value):
        self.context[key] = value
        self.save_context()

if __name__ == "__main__":
    root = tk.Tk()
    app = CMDLikeApp(root)
    root.mainloop()