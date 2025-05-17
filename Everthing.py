import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import os
import threading
import queue
from pathlib import Path
import docker

class QEMUManager:
    def __init__(self, root):
        self.root = root
        self.root.title("QEMU Virtual Machine Manager")
    
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(padx=10, pady=10, expand=True, fill='both')

        # Docker Hub Tab
        self.docker_hub_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.docker_hub_tab, text="Docker Hub")
        self.create_docker_hub_ui()

        # Virtual Disk Tab
        self.disk_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.disk_tab, text="Create Virtual Disk")
        self.create_disk_ui()

        # Virtual Machine Tab
        self.vm_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.vm_tab, text="Create Virtual Machine")
        self.create_vm_ui()

        # Dockerfile Creator Tab
        self.docker_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.docker_tab, text="Create Dockerfile")
        self.create_docker_ui()

        # Docker Image Builder Tab
        self.docker_build_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.docker_build_tab, text="Build Docker Image")
        self.create_docker_build_ui()

        # Docker Images Manager Tab
        self.docker_images_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.docker_images_tab, text="Manage Docker Images")
        self.create_docker_images_ui()

        # Docker Containers Manager Tab
        self.docker_containers_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.docker_containers_tab, text="Manage Containers")
        self.create_docker_containers_ui()

        # Console Output
        self.console = tk.Text(root, height=10)
        self.console.pack(padx=10, pady=5, fill='both')

        # Threading and queue setup
        self.docker_output_queue = queue.Queue()
        self.build_thread = None
        self.root.after(100, self.update_docker_output)
        self.root.bind("<<DockerBuildComplete>>", self.on_docker_build_complete)

        # Docker Hub queues
        self.docker_hub_search_queue = queue.Queue()
        self.docker_hub_pull_queue = queue.Queue()
        self.root.after(100, self.process_docker_hub_search)
        self.root.after(100, self.process_docker_hub_pull)

        # Initialize Docker client
        self.docker_client = None
        self.initialize_docker_client()

    def initialize_docker_client(self):
        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
        except docker.errors.DockerException as e:
            messagebox.showerror("Docker Error", f"Could not connect to Docker daemon:\n{e}")
            self.docker_client = None
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")
            self.docker_client = None

    # ----- Docker Hub Management Methods -----
    def create_docker_hub_ui(self):
        main_frame = ttk.Frame(self.docker_hub_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Search Frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=5)

        self.docker_hub_search_entry = ttk.Entry(search_frame, width=40)
        self.docker_hub_search_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.docker_hub_search_entry.bind("<Return>", lambda e: self.start_docker_hub_search())

        self.docker_hub_search_button = ttk.Button(
            search_frame, text="Search", command=self.start_docker_hub_search
        )
        self.docker_hub_search_button.pack(side=tk.LEFT, padx=5)

        self.docker_hub_pull_button = ttk.Button(
            search_frame, text="Pull Image", command=self.start_docker_hub_pull, state=tk.DISABLED
        )
        self.docker_hub_pull_button.pack(side=tk.LEFT)

        # Results Treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.docker_hub_tree = ttk.Treeview(
            tree_frame,
            columns=('name', 'description', 'stars', 'official', 'automated'),
            show='headings'
        )
        
        columns = {
            'name': ('Name', 200),
            'description': ('Description', 400),
            'stars': ('Stars', 80),
            'official': ('Official', 80),
            'automated': ('Automated', 80)
        }

        for col, (heading, width) in columns.items():
            self.docker_hub_tree.heading(col, text=heading)
            self.docker_hub_tree.column(col, width=width, anchor='center' if col in ['stars', 'official', 'automated'] else 'w')

        scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.docker_hub_tree.yview)
        scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.docker_hub_tree.xview)
        self.docker_hub_tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.docker_hub_tree.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')

        # Output Console
        self.docker_hub_output = scrolledtext.ScrolledText(
            main_frame, height=8, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 10)
        )
        self.docker_hub_output.pack(fill=tk.BOTH, expand=False, pady=5)
        self.docker_hub_output.tag_config('error', foreground='red')
        self.docker_hub_output.tag_config('success', foreground='green')

        self.docker_hub_tree.bind('<<TreeviewSelect>>', self.on_docker_hub_select)

    def on_docker_hub_select(self, event):
        selected = self.docker_hub_tree.selection()
        self.docker_hub_pull_button.config(state=tk.NORMAL if selected else tk.DISABLED)

    def start_docker_hub_search(self):
        query = self.docker_hub_search_entry.get().strip()
        if not query:
            messagebox.showwarning("Input Error", "Please enter a search query.")
            return
        self.docker_hub_search_button.config(state=tk.DISABLED)
        threading.Thread(target=self.search_docker_hub, args=(query,), daemon=True).start()

    def search_docker_hub(self, query):
        if not self.docker_client:
            self.docker_hub_search_queue.put(('error', "Docker not connected."))
            return
        try:
            results = self.docker_client.images.search(query)
            self.docker_hub_search_queue.put(('clear', None))
            for img in results:
                self.docker_hub_search_queue.put(('result', {
                    'name': img.get('name', 'N/A'),
                    'description': (img.get('description', '')[:100] + '...') if img.get('description') else '',
                    'stars': img.get('star_count', 0),
                    'official': 'Yes' if img.get('is_official') else 'No',
                    'automated': 'Yes' if img.get('is_automated') else 'No'
                }))
        except Exception as e:
            self.docker_hub_search_queue.put(('error', str(e)))
        finally:
            self.docker_hub_search_queue.put(('done', None))

    def process_docker_hub_search(self):
        try:
            while True:
                task, data = self.docker_hub_search_queue.get_nowait()
                if task == 'result':
                    self.docker_hub_tree.insert('', 'end', values=(
                        data['name'], data['description'], data['stars'], data['official'], data['automated']
                    ))
                elif task == 'error':
                    self.append_docker_hub_output(data, 'error')
                elif task == 'clear':
                    self.docker_hub_tree.delete(*self.docker_hub_tree.get_children())
                elif task == 'done':
                    self.docker_hub_search_button.config(state=tk.NORMAL)
        except queue.Empty:
            pass
        self.root.after(100, self.process_docker_hub_search)

    def start_docker_hub_pull(self):
        selected = self.docker_hub_tree.selection()
        if not selected:
            return
        image_name = self.docker_hub_tree.item(selected[0], 'values')[0]
        self.docker_hub_pull_button.config(state=tk.DISABLED)
        threading.Thread(target=self.pull_docker_image, args=(image_name,), daemon=True).start()

    def pull_docker_image(self, image_name):
        if not self.docker_client:
            self.docker_hub_pull_queue.put(('error', "Docker not connected."))
            return
        try:
            self.docker_hub_output.config(state=tk.NORMAL)
            self.docker_hub_output.delete(1.0, tk.END)
            self.docker_hub_output.insert(tk.END, f"Pulling {image_name}...\n")
            self.docker_hub_output.config(state=tk.DISABLED)
            for line in self.docker_client.api.pull(image_name, stream=True, decode=True):
                self.docker_hub_pull_queue.put(line)
            self.docker_hub_pull_queue.put(('success', f"Successfully pulled {image_name}"))
        except Exception as e:
            self.docker_hub_pull_queue.put(('error', str(e)))
        finally:
            self.docker_hub_pull_queue.put(('done', None))

    def process_docker_hub_pull(self):
        try:
            while True:
                item = self.docker_hub_pull_queue.get_nowait()
                if isinstance(item, dict):
                    self.append_docker_hub_output(f"Status: {item.get('status', '')}")
                    if 'progress' in item:
                        self.append_docker_hub_output(f"Progress: {item['progress']}")
                elif isinstance(item, tuple):
                    status, msg = item
                    self.append_docker_hub_output(msg, tag=status)
                elif item == 'done':
                    self.docker_hub_pull_button.config(state=tk.NORMAL)
        except queue.Empty:
            pass
        self.root.after(100, self.process_docker_hub_pull)

    def append_docker_hub_output(self, text, tag=None):
        self.docker_hub_output.config(state=tk.NORMAL)
        self.docker_hub_output.insert(tk.END, text + "\n", tag)
        self.docker_hub_output.see(tk.END)
        self.docker_hub_output.config(state=tk.DISABLED)

    # ----- Original Disk Management Methods -----
    def create_disk_ui(self):
        formats = ['qcow2', 'raw', 'vdi', 'vmdk']
        allocation_types = ['Dynamic', 'Fixed']

        ttk.Label(self.disk_tab, text="Filename:").grid(row=0, column=0, padx=5, pady=5)
        self.disk_filename = ttk.Entry(self.disk_tab, width=30)
        self.disk_filename.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.disk_tab, text="Browse", command=self.browse_disk_path).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(self.disk_tab, text="Size:").grid(row=1, column=0, padx=5, pady=5)
        self.disk_size = ttk.Entry(self.disk_tab, width=10, validate='key')
        self.disk_size['validatecommand'] = (self.disk_size.register(self.validate_disk_size), '%P')
        self.disk_size.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        self.size_unit = ttk.Combobox(self.disk_tab, values=['G', 'M'], width=2)
        self.size_unit.set('G')
        self.size_unit.grid(row=1, column=1, padx=5, pady=5, sticky='e')

        ttk.Label(self.disk_tab, text="Format:").grid(row=2, column=0, padx=5, pady=5)
        self.disk_format = ttk.Combobox(self.disk_tab, values=formats)
        self.disk_format.set('qcow2')
        self.disk_format.grid(row=2, column=1, padx=5, pady=5, sticky='w')

        ttk.Label(self.disk_tab, text="Allocation:").grid(row=3, column=0, padx=5, pady=5)
        self.allocation_type = ttk.Combobox(self.disk_tab, values=allocation_types)
        self.allocation_type.set('Dynamic')
        self.allocation_type.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        ttk.Button(self.disk_tab, text="Create Disk", command=self.create_disk).grid(row=4, column=1, padx=5, pady=10)

    def validate_disk_size(self, value):
        if value == "": return True
        try: return float(value) > 0
        except ValueError: return False

    def browse_disk_path(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".qcow2",
            filetypes=[("QEMU Disk Images", "*.qcow2 *.raw *.vdi *.vmdk"), ("All Files", "*.*")]
        )
        if filename:
            self.disk_filename.delete(0, tk.END)
            self.disk_filename.insert(0, filename)

    def create_disk(self):
        filename = self.disk_filename.get()
        size = self.disk_size.get()
        unit = self.size_unit.get()
        format = self.disk_format.get()
        allocation = self.allocation_type.get()

        try:
            if not all([filename, size, format]) or float(size) <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Invalid disk parameters")
            return

        allocation_map = {
            'qcow2': {'Dynamic': 'preallocation=off', 'Fixed': 'preallocation=metadata'},
            'raw': {'Dynamic': '', 'Fixed': ''},
            'vdi': {'Dynamic': '', 'Fixed': ''},
            'vmdk': {'Dynamic': '', 'Fixed': ''}
        }

        cmd = f'qemu-img create -f {format}'
        if options := allocation_map.get(format, {}).get(allocation):
            cmd += f' -o {options}'
        cmd += f' {filename} {size}{unit}'

        try:    
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            self.console.insert(tk.END, f"Disk created: {cmd}\n{result.stdout}\n")
        except subprocess.CalledProcessError as e:
            error_msg = f"Error creating disk:\n{e.stderr}\n"
            if "preallocation=full" in error_msg and format == 'raw':
                error_msg += "\nTIP: Raw format doesn't support full preallocation. Use Dynamic allocation instead."
            self.console.insert(tk.END, error_msg)

    # ----- Original VM Management Methods -----
    def create_vm_ui(self):
        ttk.Label(self.vm_tab, text="CPU Cores:").grid(row=0, column=0, padx=5, pady=5)
        self.vm_cpu = ttk.Entry(self.vm_tab, validate='key')
        self.vm_cpu['validatecommand'] = (self.vm_cpu.register(self.validate_numeric_input), '%P')
        self.vm_cpu.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(self.vm_tab, text="Memory (MB):").grid(row=1, column=0, padx=5, pady=5)
        self.vm_memory = ttk.Entry(self.vm_tab, validate='key')
        self.vm_memory['validatecommand'] = (self.vm_memory.register(self.validate_numeric_input), '%P')
        self.vm_memory.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(self.vm_tab, text="Virtual Disk:").grid(row=2, column=0, padx=5, pady=5)
        self.vm_disk_path = ttk.Entry(self.vm_tab, width=30)
        self.vm_disk_path.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(self.vm_tab, text="Browse", command=self.browse_vm_disk).grid(row=2, column=2, padx=5, pady=5)

        ttk.Label(self.vm_tab, text="Disk Format:").grid(row=3, column=0, padx=5, pady=5)
        self.vm_disk_format = ttk.Combobox(self.vm_tab, values=['qcow2', 'raw', 'vdi', 'vmdk'])
        self.vm_disk_format.set('qcow2')
        self.vm_disk_format.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(self.vm_tab, text="ISO Image:").grid(row=4, column=0, padx=5, pady=5)
        self.iso_path = ttk.Entry(self.vm_tab, width=30)
        self.iso_path.grid(row=4, column=1, padx=5, pady=5)
        ttk.Button(self.vm_tab, text="Browse", command=self.browse_iso).grid(row=4, column=2, padx=5, pady=5)

        ttk.Button(self.vm_tab, text="Create VM", command=self.create_vm).grid(row=5, column=1, padx=5, pady=10)

    def validate_numeric_input(self, value):
        if value == "": return True
        try: return int(value) > 0
        except ValueError: return False

    def browse_vm_disk(self):
        filename = filedialog.askopenfilename(
            filetypes=[("Disk Images", "*.qcow2 *.raw *.vdi *.vmdk"), ("All Files", "*.*")]
        )
        if filename:
            self.vm_disk_path.delete(0, tk.END)
            self.vm_disk_path.insert(0, filename)
            ext = os.path.splitext(filename)[1][1:].lower()
            if ext in ['qcow2', 'raw', 'vdi', 'vmdk']:
                self.vm_disk_format.set(ext)

    def browse_iso(self):
        filename = filedialog.askopenfilename(
            filetypes=[("ISO Images", "*.iso"), ("All Files", "*.*")]
        )
        if filename:
            self.iso_path.delete(0, tk.END)
            self.iso_path.insert(0, filename)

    def create_vm(self):
        try:
            cpu = int(self.vm_cpu.get())
            memory = int(self.vm_memory.get())
            if cpu <= 0 or memory <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Invalid CPU/Memory values")
            return

        disk_path = self.vm_disk_path.get()
        disk_format = self.vm_disk_format.get()
        iso_path = self.iso_path.get()

        if not all([disk_path, iso_path]) or not os.path.exists(disk_path) or not os.path.exists(iso_path):
            messagebox.showerror("Error", "Invalid disk or ISO path")
            return

        cmd = (
            f'qemu-system-x86_64 -smp {cpu} -m {memory} '
            f'-drive file="{disk_path}",format={disk_format} '
            f'-cdrom "{iso_path}" -boot menu=on '
            f'-display gtk -machine type=q35 -usbdevice tablet'
        )

        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.console.insert(tk.END, f"Starting VM: {cmd}\n")
            
            def read_output():
                while True:
                    output = process.stdout.readline()
                    error = process.stderr.readline()
                    if not output and not error and process.poll() is not None:
                        break
                    if output: self.console.insert(tk.END, f"OUT: {output}")
                    if error: self.console.insert(tk.END, f"ERR: {error}")
                    self.console.see(tk.END)

            threading.Thread(target=read_output, daemon=True).start()
        except Exception as e:
            self.console.insert(tk.END, f"VM Error: {str(e)}\n")

    # ----- Original Docker Management Methods -----
    def create_docker_ui(self):
        ttk.Label(self.docker_tab, text="Save Path:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.docker_path_entry = ttk.Entry(self.docker_tab, width=50)
        self.docker_path_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(self.docker_tab, text="Browse", command=self.browse_docker_directory).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(self.docker_tab, text="Dockerfile Content:").grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='w')
        self.docker_content_text = scrolledtext.ScrolledText(
            self.docker_tab,
            wrap=tk.WORD,
            font=('Consolas', 10),
            undo=True
        )
        self.docker_content_text.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')

        button_frame = ttk.Frame(self.docker_tab)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)
        ttk.Button(button_frame, text="Save Dockerfile", command=self.save_dockerfile).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Clear Content", command=self.clear_docker_content).pack(side=tk.LEFT, padx=5)

        self.docker_tab.grid_rowconfigure(2, weight=1)
        self.docker_tab.grid_columnconfigure(1, weight=1)
        self.insert_docker_template()

    def browse_docker_directory(self):
        path = filedialog.askdirectory()
        if path:
            self.docker_path_entry.delete(0, tk.END)
            self.docker_path_entry.insert(0, path)

    def insert_docker_template(self):
        template = """FROM python:3.9-slim

# Add these environment variables
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "app.py"]"""
        self.docker_content_text.insert(tk.END, template)

    def clear_docker_content(self):
        self.docker_content_text.delete(1.0, tk.END)

    def save_dockerfile(self):
        save_path = self.docker_path_entry.get()
        content = self.docker_content_text.get(1.0, tk.END).strip()

        if not save_path or not content:
            messagebox.showwarning("Error", "Missing path or content")
            return

        full_path = os.path.join(save_path, "Dockerfile")
        if os.path.exists(full_path) and not messagebox.askyesno("Overwrite", "Overwrite existing Dockerfile?"):
            return

        try:
            with open(full_path, 'w') as f:
                f.write(content)
            messagebox.showinfo("Success", f"Dockerfile saved at:\n{full_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {str(e)}")

    def create_docker_build_ui(self):
        ttk.Label(self.docker_build_tab, text="Dockerfile Path:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.dockerfile_entry = ttk.Entry(self.docker_build_tab, width=50)
        self.dockerfile_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(self.docker_build_tab, text="Browse", command=self.browse_dockerfile).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(self.docker_build_tab, text="Image Name/Tag:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.image_entry = ttk.Entry(self.docker_build_tab, width=50)
        self.image_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky='ew')

        self.docker_build_button = ttk.Button(
            self.docker_build_tab,
            text="Build Image",
            command=self.start_docker_build_thread
        )
        self.docker_build_button.grid(row=2, column=1, pady=10)

        self.docker_output_text = tk.Text(
            self.docker_build_tab,
            wrap=tk.NONE,
            font=('Courier New', 10),
            state=tk.DISABLED
        )
        self.docker_output_text.grid(row=3, column=0, columnspan=3, sticky='nsew', padx=5, pady=5)

        scroll_y = ttk.Scrollbar(self.docker_build_tab, orient=tk.VERTICAL, command=self.docker_output_text.yview)
        scroll_y.grid(row=3, column=3, sticky='ns')

        scroll_x = ttk.Scrollbar(self.docker_build_tab, orient=tk.HORIZONTAL, command=self.docker_output_text.xview)
        scroll_x.grid(row=4, column=0, columnspan=3, sticky='ew')

        self.docker_output_text.config(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.docker_build_tab.grid_rowconfigure(3, weight=1)
        self.docker_build_tab.grid_columnconfigure(1, weight=1)

    def browse_dockerfile(self):
        file_path = filedialog.askopenfilename(
            title="Select Dockerfile",
            filetypes=[("Dockerfiles", "Dockerfile*"), ("All files", "*")]
        )
        if file_path:
            self.dockerfile_entry.delete(0, tk.END)
            self.dockerfile_entry.insert(0, file_path)

    def start_docker_build_thread(self):
        dockerfile_path = self.dockerfile_entry.get()
        image_name = self.image_entry.get()

        if not dockerfile_path or not image_name or not Path(dockerfile_path).exists():
            messagebox.showerror("Error", "Invalid Dockerfile path or image name")
            return

        self.docker_output_text.config(state=tk.NORMAL)
        self.docker_output_text.delete(1.0, tk.END)
        self.docker_output_text.insert(tk.END, "Starting build...\n")
        self.docker_output_text.config(state=tk.DISABLED)
        self.docker_build_button.config(state=tk.DISABLED)

        self.build_thread = threading.Thread(
            target=self.build_docker_image,
            args=(dockerfile_path, image_name),
            daemon=True
        )
        self.build_thread.start()

    def build_docker_image(self, dockerfile_path, image_name):
        try:
            build_context = str(Path(dockerfile_path).parent)
            command = [
                'docker', 'build',
                '-f', dockerfile_path,
                '-t', image_name,
                build_context
            ]

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in iter(process.stdout.readline, ''):
                self.docker_output_queue.put(line)

            process.stdout.close()
            return_code = process.wait()

            if return_code == 0:
                self.docker_output_queue.put("\nBuild successful!\n")
            else:
                self.docker_output_queue.put(f"\nBuild failed (code {return_code})\n")

        except Exception as e:
            self.docker_output_queue.put(f"\nError: {str(e)}\n")
        finally:
            self.docker_output_queue.put(None)
            self.root.event_generate("<<DockerBuildComplete>>")

    def update_docker_output(self):
        try:
            while True:
                line = self.docker_output_queue.get_nowait()
                if line is None: break
                self.docker_output_text.config(state=tk.NORMAL)
                self.docker_output_text.insert(tk.END, line)
                self.docker_output_text.see(tk.END)
                self.docker_output_text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.root.after(100, self.update_docker_output)

    def on_docker_build_complete(self, event):
        self.docker_build_button.config(state=tk.NORMAL)

    def create_docker_images_ui(self):
        search_frame = ttk.Frame(self.docker_images_tab)
        search_frame.pack(fill=tk.X, pady=5)

        self.docker_search_entry = ttk.Entry(search_frame, width=40)
        self.docker_search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.docker_search_entry.bind("<Return>", lambda e: self.list_docker_images())

        ttk.Button(search_frame, text="Search Images", command=self.list_docker_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="List All Images", command=self.show_all_docker_images).pack(side=tk.LEFT)

        tree_frame = ttk.Frame(self.docker_images_tab)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.docker_tree = ttk.Treeview(
            tree_frame,
            columns=('repository', 'tag', 'image_id', 'created', 'size'),
            show='headings'
        )

        columns = {
            'repository': ('Repository', 200),
            'tag': ('Tag', 100),
            'image_id': ('Image ID', 200),
            'created': ('Created', 150),
            'size': ('Size', 100)
        }

        for col, (text, width) in columns.items():
            self.docker_tree.heading(col, text=text)
            self.docker_tree.column(col, width=width)

        scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.docker_tree.yview)
        scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.docker_tree.xview)
        self.docker_tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.docker_tree.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def list_docker_images(self):
        search_term = self.docker_search_entry.get().strip()
        try:
            cmd = ['docker', 'images', '--format', 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}']
            if search_term:
                cmd.extend(['--filter', f'reference=*{search_term}*'])

            result = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
            self.update_docker_treeview(result)
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to list images:\n{e.output or str(e)}")
        except FileNotFoundError:
            messagebox.showerror("Error", "Docker not found")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error:\n{str(e)}")

    def show_all_docker_images(self):
        self.docker_search_entry.delete(0, tk.END)
        self.list_docker_images()

    def update_docker_treeview(self, content):
        self.docker_tree.delete(*self.docker_tree.get_children())
        for line in content.strip().split('\n')[1:]:
            if parts := line.split(maxsplit=4):
                self.docker_tree.insert('', tk.END, values=(
                    parts[0], 
                    parts[1] if len(parts) > 1 else '',
                    parts[2] if len(parts) > 2 else '',
                    parts[3] if len(parts) > 3 else '',
                    parts[4] if len(parts) > 4 else ''
                ))

    # ----- Docker Containers Management Methods (Fixed) -----
    def create_docker_containers_ui(self):
        main_frame = ttk.Frame(self.docker_containers_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)

        self.container_refresh_button = ttk.Button(
            control_frame,
            text="Refresh Containers",
            command=self.start_container_refresh_thread
        )
        self.container_refresh_button.pack(side=tk.LEFT, padx=5)

        self.container_stop_button = ttk.Button(
            control_frame,
            text="Stop Container",
            command=self.start_container_stop_thread,
            state=tk.DISABLED
        )
        self.container_stop_button.pack(side=tk.LEFT)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.container_tree = ttk.Treeview(
            tree_frame,
            columns=('id', 'name', 'status', 'image', 'ports', 'created'),
            show='headings',
            selectmode='browse'
        )

        columns = {
            'id': ('Container ID', 200),
            'name': ('Name', 150),
            'status': ('Status', 100),
            'image': ('Image', 200),
            'ports': ('Ports', 150),
            'created': ('Created', 150)
        }

        for col, (heading, width) in columns.items():
            self.container_tree.heading(col, text=heading)
            self.container_tree.column(col, width=width, anchor='w')

        scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.container_tree.yview)
        scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.container_tree.xview)
        self.container_tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.container_tree.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.container_status_var = tk.StringVar()
        container_status_bar = ttk.Label(self.docker_containers_tab, 
                                       textvariable=self.container_status_var, 
                                       relief=tk.SUNKEN)
        container_status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.container_tree.bind('<<TreeviewSelect>>', self.on_container_tree_select)
        
        # Container management queue setup
        self.container_queue = queue.Queue()
        self.root.after(100, self.process_container_queue)
        

    def process_container_queue(self):
        try:
            while True:
                item = self.container_queue.get_nowait()
                if item[0] == 'container':
                    self.container_tree.insert('', tk.END, values=(
                        item[1]['id'],
                        item[1]['name'],
                        item[1]['status'],
                        item[1]['image'],
                        item[1]['ports'],
                        item[1]['created']
                    ))
                elif item[0] == 'error':
                    messagebox.showerror("Error", item[1])
                elif item[0] == 'success':
                    self.container_status_var.set(item[1])
                elif item[0] == 'refresh':
                    self.start_container_refresh_thread()
                elif item[0] == 'clear':
                    self.container_tree.delete(*self.container_tree.get_children())
                elif item[0] == 'done':
                    self.container_refresh_button.config(state=tk.NORMAL)
                    self.container_stop_button.config(state=tk.DISABLED)
                    count = len(self.container_tree.get_children())
                    self.container_status_var.set(f"Found {count} running containers")
        except queue.Empty:
            pass
        self.root.after(100, self.process_container_queue)

    def on_container_tree_select(self, event):
        selected = self.container_tree.selection()
        self.container_stop_button.config(state=tk.NORMAL if selected else tk.DISABLED)

    def get_selected_container_id(self):
        selected = self.container_tree.selection()
        return self.container_tree.item(selected[0], 'values')[0] if selected else None

    def start_container_refresh_thread(self):
        self.container_refresh_button.config(state=tk.DISABLED)
        self.container_status_var.set("Refreshing container list...")
        threading.Thread(target=self.refresh_containers, daemon=True).start()

    def refresh_containers(self):
        if self.docker_client is None:
            self.container_queue.put(('error', "Docker connection not available"))
            return
        try:
            containers = self.docker_client.containers.list(filters={'status': 'running'})
            self.container_queue.put(('clear', None))
            
            for container in containers:
                attrs = container.attrs
                self.container_queue.put(('container', {
                    'id': container.short_id,
                    'name': container.name,
                    'status': container.status,
                    'image': container.image.tags[0] if container.image.tags else container.image.id,
                    'ports': "\n".join(attrs['NetworkSettings']['Ports'].keys()) if attrs['NetworkSettings']['Ports'] else "None",
                    'created': attrs['Created'][:19]
                }))
                
        except docker.errors.APIError as e:
            self.container_queue.put(('error', f"Docker API Error: {e}"))
        except Exception as e:
            self.container_queue.put(('error', f"Error refreshing containers: {str(e)}"))
        finally:
            self.container_queue.put(('done', None))

    def start_container_stop_thread(self):
        if (container_id := self.get_selected_container_id()):
            if messagebox.askyesno("Confirm Stop", "Are you sure you want to stop this container?"):
                self.container_stop_button.config(state=tk.DISABLED)
                self.container_status_var.set(f"Stopping container {container_id}...")
                threading.Thread(target=self.stop_container, args=(container_id,), daemon=True).start()

    def stop_container(self, container_id):
        try:
            container = self.docker_client.containers.get(container_id)
            container.stop()
            self.container_queue.put(('success', f"Successfully stopped container {container_id}"))
            self.container_queue.put(('refresh', None))
        except docker.errors.NotFound:
            self.container_queue.put(('error', f"Container {container_id} no longer exists"))
        except Exception as e:
            self.container_queue.put(('error', f"Error stopping container: {str(e)}"))
        finally:
            self.container_queue.put(('done', None))

if __name__ == "__main__":
    root = tk.Tk()
    app = QEMUManager(root)
    root.mainloop()