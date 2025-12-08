import subprocess
import time
import select
import re

class GAP:
    def __init__(self, gap_executable="gap"):
        """
        Initialize a GAP session.
        
        Args:
            gap_executable: Path to the GAP executable (default: "gap")
        """
        # Start GAP process
        self.process = subprocess.Popen(
            [gap_executable, "-b"],  # -b for no banner
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0  # Unbuffered
        )
        
        # Wait for GAP to start up and consume initial output
        time.sleep(0.5)
        self._clear_output()
        
        # Disable breaking on errors
        self("BreakOnError := false;;")
        
    def _clear_output(self):
        """Clear any pending output."""
        while True:
            ready, _, _ = select.select([self.process.stdout], [], [], 0.1)
            if not ready:
                break
            self.process.stdout.readline()
    
    def __call__(self, command):
        """
        Execute a GAP command and return the result.
        
        Args:
            command: GAP command string
            
        Returns:
            The output from GAP
        """
        
        # Restart gap if it has terminated
        if self.process.poll() is not None:
            self.__init__()
        
        if command.startswith("?"):
            raise ValueError("GAP wrapper does not support help commands.")
        
        if command.startswith("QUIT") or command.startswith("quit"):
            raise ValueError("This Code would terminate the GAP session.")
        
        # Ensure command ends with semicolon
        if not command.strip().endswith(';'):
            command = command.strip() + ';'
        
        # Use a unique marker to detect end of output
        marker = "___PYTHON_GAP_MARKER___"
        
        try:
          # Send command followed by a Print statement with our marker
          self.process.stdin.write(command + '\n')
          self.process.stdin.write(f'Print("{marker}\\n");\n')
          self.process.stdin.write(f'Error("{marker}\\n");\n')
          
          self.process.stdin.flush()
        except BrokenPipeError:
          raise RuntimeError("GAP process has terminated unexpectedly.")
        
        # Read output until we see our marker
        output_lines = []
        while True:
            output_line = self.process.stdout.readline()
            if marker in output_line:
                break
            if output_line:
                # Remove ANSI escape codes using regex
                output_line = re.sub(r'\033\[[0-9;]*m', '', output_line)
                output_line = output_line.replace('gap> ', '')
                output_lines.append(output_line.rstrip())
        
        # Read any error output
        error_output = []
        while True:
            err_line = self.process.stderr.readline()
            if marker in err_line:
                break
            if err_line:
                # Remove ANSI escape codes using regex
                err_line = re.sub(r'\033\[[0-9;]*m', '', err_line)
                error_output.append(err_line.rstrip())
        
        # Join and clean up the output
        result = '\n'.join(output_lines).strip()
        errors = '\n'.join(error_output).strip()
        
        if errors:
          raise RuntimeError(f"GAP Error: {errors}")
        elif result:
            return result
        else:
            return "No output!"
    
    def __rshift__(self, cmd):
        return self(cmd)
    
    def close(self):
        """Close the GAP session."""
        if self.process:
            try:
                self.process.stdin.write('quit;\n')
                self.process.stdin.flush()
            except:
                pass
            self.process.terminate()
            self.process.wait(timeout=2)
    
    def __enter__(self):
        """Support context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up when exiting context."""
        self.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()
    
    def restart(self):
        """Restart the GAP session."""
        self.close()
        self.__init__()

def main():
    with GAP() as gap:
        print("GAP version:")
        print(gap("Version();"))
        
        print("\nDefining a group:")
        print(gap("G := SymmetricGroup(3);"))
        
        print("\nElements of the group:")
        print(gap("Elements(G);"))
        
        print("\nOrder of the group:")
        print(gap("Size(G);"))

if __name__ == "__main__":
    main()