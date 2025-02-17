from pathlib import Path
from typing import Dict, Optional
import openai
from os import getenv
import os

class RepositoryAgent:
    def __init__(self, repository_path: Path):
        self.repository_path = repository_path
        self.analysis_results = {}
        openai.api_key = getenv("OPENAI_API_KEY")

    def read_repository_contents(self) -> str:
        """Read all relevant code files from the repository."""
        code_contents = []
        # File extensions to read
        code_extensions = {'.py', '.js', '.java', '.cpp', '.h', '.cs', '.php', '.rb', '.go', '.rs', 
                         '.ts', '.html', '.css', '.sql', '.md', '.json', '.yaml', '.yml'}
        
        for file_path in self.repository_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in code_extensions:
                # Skip virtual environments and node_modules
                if any(part in str(file_path) for part in ['venv', 'node_modules', '__pycache__', '.git']):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        relative_path = file_path.relative_to(self.repository_path)
                        code_contents.append(f"\n--- {relative_path} ---\n")
                        code_contents.append(file.read())
                except Exception as e:
                    code_contents.append(f"\nError reading {file_path}: {str(e)}\n")
        
        return "\n".join(code_contents)

    def analyze_repository(self) -> Dict:
        """
        Analyze the repository structure and contents.

        Returns:
            Dict: Analysis results including file structure and basic stats
        """
        try:
            # Get repository structure
            files = list(self.repository_path.rglob("*"))

            # Basic statistics
            stats = {
                "total_files": len([f for f in files if f.is_file()]),
                "total_directories": len([f for f in files if f.is_dir()]),
                "file_types": {},
                "repository_name": self.repository_path.name
            }

            # Count file types
            for file in files:
                if file.is_file():
                    file_type = file.suffix
                    stats["file_types"][file_type] = stats["file_types"].get(file_type, 0) + 1

            self.analysis_results = stats
            return {
                "status": "success",
                "results": stats
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error analyzing repository: {str(e)}"
            }

    async def process_prompt(self, prompt: str) -> Dict:
        """Process a user prompt about the repository using GPT."""
        try:
            # Read repository contents
            code_contents = self.read_repository_contents()
            
            # Prepare the message for GPT
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant that analyzes code repositories and answers questions about them. Provide clear, concise answers and include relevant code snippets when appropriate."},
                {"role": "user", "content": f"Here is the repository content:\n\n{code_contents}\n\nUser question: {prompt}"}
            ]
            
            # Call GPT
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )
            
            return {
                "status": "success",
                "response": response.choices[0].message.content
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing prompt: {str(e)}"
            }

class AgentOrchestrator:
    def __init__(self):
        self.uploads_dir = Path("uploads")

    def list_repositories(self) -> list:
        """List all available repositories in the uploads directory."""
        if not self.uploads_dir.exists():
            return []
        return [d.name for d in self.uploads_dir.iterdir() if d.is_dir()]

    def get_repository_path(self, repository_name: str) -> Optional[Path]:
        """Get the path to a specific repository."""
        repo_path = self.uploads_dir / repository_name
        return repo_path if repo_path.exists() else None

    async def process_repository_prompt(self, repository_name: str, prompt: str) -> Dict:
        """Process a prompt for a specific repository."""
        repo_path = self.get_repository_path(repository_name)
        if not repo_path:
            return {
                "status": "error",
                "message": f"Repository '{repository_name}' not found"
            }
        
        agent = RepositoryAgent(repo_path)
        return await agent.process_prompt(prompt)
