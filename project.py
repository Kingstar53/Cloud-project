import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import threading

class QEMUManager:
    def __init__(self, root):
        self.root = root
        self.root.title("QEMU Virtual Machine Manager")
        
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(padx=10, pady=10, expand=True, fill='both')

       
        self.disk_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.disk_tab, text="Create Virtual Disk")
        self.create_disk_ui()

       
        self.vm_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.vm_tab, text="Create Virtual Machine")
        self.create_vm_ui()

        
        self.console = tk.Text(root, height=10)
        self.console.pack(padx=10, pady=5, fill='both')

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
        if value == "":
            return True
        try:
            return int(value) > 0
        except ValueError:
            return False

    def validate_disk_size(self, value):
        """Validate disk size input (positive numbers with optional decimals)"""
        if value == "":
            return True
        try:
            return float(value) > 0
        except ValueError:
            return False

    def browse_disk_path(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".qcow2",
            filetypes=[("QEMU Disk Images", "*.qcow2 *.raw *.vdi *.vmdk"), ("All Files", "*.*")]
        )
        if filename:
            self.disk_filename.delete(0, tk.END)
            self.disk_filename.insert(0, filename)

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

    def create_disk(self):
        filename = self.disk_filename.get()
        size = self.disk_size.get()
        unit = self.size_unit.get()
        format = self.disk_format.get()
        allocation = self.allocation_type.get()

       
        try:
            size_float = float(size)
            if size_float <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Disk size must be a positive number")
            return

        if not all([filename, size, format]):
            messagebox.showerror("Error", "Please fill all fields")
            return

        
        allocation_map = {
            'qcow2': {
                'Dynamic': 'preallocation=off',
                'Fixed': 'preallocation=metadata'
            },
            'raw': {
                'Dynamic': '',
                'Fixed': 'preallocation=full'
            },
            'vdi': {'Dynamic': '', 'Fixed': ''},
            'vmdk': {'Dynamic': '', 'Fixed': ''}
        }

        try:
            options = allocation_map[format][allocation]
        except KeyError:
            options = ''

        cmd = f'C:\\msys64\\ucrt64\\bin\\qemu-img.exe create -f {format}'
        if options:
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

    def create_vm(self):
        try:
            cpu = int(self.vm_cpu.get())
            memory = int(self.vm_memory.get())
            if cpu <= 0 or memory <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "CPU and Memory must be positive numbers")
            return

        disk_path = self.vm_disk_path.get()
        disk_format = self.vm_disk_format.get()
        iso_path = self.iso_path.get()

        if not all([disk_path, iso_path]):
            messagebox.showerror("Error", "Please select both a disk and ISO image")
            return

        if disk_format not in ['qcow2', 'raw', 'vdi', 'vmdk']:
            messagebox.showerror("Error", "Invalid disk format selected")
            return

        if not os.path.exists(disk_path):
            messagebox.showerror("Error", "Selected disk does not exist")
            return

        if not os.path.exists(iso_path):
            messagebox.showerror("Error", "Selected ISO does not exist")
            return

        
        cmd = (
            f'C:\\msys64\\ucrt64\\bin\\qemu-system-x86_64.exe '
            f'-smp {cpu} -m {memory} '
            f'-drive file="{disk_path}",format={disk_format} '
            f'-cdrom "{iso_path}" '
            f'-boot menu=on '
            f'-display gtk '
            f'-machine type=q35 '
            f'-usbdevice tablet'
        )

        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.console.insert(tk.END, f"Starting VM with command:\n{cmd}\n")
            
            def read_output():
                while True:
                    output = process.stdout.readline()
                    error = process.stderr.readline()
                    if not output and not error and process.poll() is not None:
                        break
                    if output:
                        self.console.insert(tk.END, f"OUT: {output}")
                    if error:
                        self.console.insert(tk.END, f"ERR: {error}")
                    self.console.see(tk.END)

            threading.Thread(target=read_output, daemon=True).start()

        except Exception as e:
            self.console.insert(tk.END, f"Error starting VM: {str(e)}\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = QEMUManager(root)
    root.mainloop()