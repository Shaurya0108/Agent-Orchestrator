from pathlib import Path
from typing import Dict, Optional, List
import openai
from os import getenv
import os
import logging
import json
import shutil
from agents.agent_selector import AgentSelector
from agents.base_agent import BaseAgent
from agents.tools.code_change import CodeChangeHandler

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class RepositoryAnalysisAgent(BaseAgent):
    def __init__(self, repository_path: Path):
        super().__init__("Repository Analysis Agent")
        self.repository_path = repository_path
        self.analysis_results = {}

    async def process(self, context: Dict) -> Dict:
        try:
            files = list(self.repository_path.rglob("*"))
            stats = {
                "total_files": len([f for f in files if f.is_file()]),
                "total_directories": len([f for f in files if f.is_dir()]),
                "file_types": {},
                "repository_name": self.repository_path.name
            }

            for file in files:
                if file.is_file():
                    file_type = file.suffix
                    stats["file_types"][file_type] = stats["file_types"].get(file_type, 0) + 1

            logger.debug(f"{self.name}: Analysis completed successfully")
            return {"status": "success", "results": stats}
        except Exception as e:
            logger.error(f"{self.name}: Error during analysis - {str(e)}")
            return {"status": "error", "message": str(e)}

class CodeReaderAgent(BaseAgent):
    def __init__(self, repository_path: Path):
        super().__init__("Code Reader Agent")
        self.repository_path = repository_path

    async def process(self, context: Dict) -> Dict:
        logger.debug(f"{self.name}: Starting code reading")
        code_contents = []
        code_extensions = {'.py', '.js', '.java', '.cpp', '.h', '.cs', '.php', '.rb', '.go', '.rs', '.ts', '.html', '.css', '.sql', '.md', '.json', '.yaml', '.yml'}

        try:
            for file_path in self.repository_path.rglob("*"):
                if file_path.is_file() and file_path.suffix in code_extensions:
                    if any(part in str(file_path) for part in ['venv', 'node_modules', '__pycache__', '.git']):
                        continue

                    # logger.debug(f"{self.name}: Reading file {file_path.relative_to(self.repository_path)}")
                    try:
                        with open(file_path, 'r', encoding='utf-8') as file:
                            relative_path = file_path.relative_to(self.repository_path)
                            code_contents.append(f"\n--- {relative_path} ---\n")
                            code_contents.append(file.read())
                    except Exception as e:
                        logger.warning(f"{self.name}: Error reading {file_path}: {str(e)}")
                        code_contents.append(f"\nError reading {file_path}: {str(e)}\n")

            logger.debug(f"{self.name}: Completed reading all files")
            return {"status": "success", "code_contents": "\n".join(code_contents)}
        except Exception as e:
            logger.error(f"{self.name}: Error during code reading - {str(e)}")
            return {"status": "error", "message": str(e)}

class PlannerAgent(BaseAgent):
    """Creates a structured plan for code analysis"""
    def __init__(self):
        super().__init__("Planner Agent")
        openai.api_key = getenv("OPENAI_API_KEY")

    async def process(self, context: Dict) -> Dict:
        logger.debug(f"{self.name}: Starting planning process")
        try:
            analysis_results = context.get("results", {})
            prompt = context.get("prompt", "")

            # Create a planning prompt
            planning_prompt = f"""
Based on the repository analysis and user question, create a structured plan for code review.

Repository Statistics:
- Total Files: {analysis_results.get('total_files', 0)}
- Total Directories: {analysis_results.get('total_directories', 0)}
- File Types: {analysis_results.get('file_types', {})}

User Question: {prompt}

Create a structured plan that includes:
1. Key areas of the codebase to focus on
2. Specific aspects to analyze
3. Order of analysis
4. Expected insights to look for
5. How to structure the response

Provide the plan in a clear, structured format.
"""

            logger.debug(f"{self.name}: Sending planning request to OpenAI")
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert code reviewer and technical architect. Create structured plans for code analysis."},
                    {"role": "user", "content": planning_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            plan = response.choices[0].message.content
            logger.debug(f"{self.name}: Plan created successfully")
            return {
                "status": "success",
                "plan": plan
            }

        except Exception as e:
            logger.error(f"{self.name}: Error during planning - {str(e)}")
            return {"status": "error", "message": str(e)}

class GPTAgent(BaseAgent):
    def __init__(self, repository_path: Optional[Path] = None):
        super().__init__("GPT Agent")
        openai.api_key = getenv("OPENAI_API_KEY")
        self.repository_path = repository_path
        logger.debug(f"{self.name}: Initialized with repository path: {repository_path}")
        self.code_handler = CodeChangeHandler(repository_path) if repository_path else None
        if not self.code_handler:
            logger.warning(f"{self.name}: No CodeChangeHandler initialized - code changes will not be applied")

    async def process(self, context: Dict) -> Dict:
        logger.debug(f"{self.name}: Starting GPT processing")
        try:
            code_contents = context.get("code_contents", "")
            prompt = context.get("prompt", "")
            plan = context.get("plan", "")

            logger.info(f"{self.name}: Processing prompt: {prompt}")
            logger.info(f"{self.name}: Using plan: {plan}")

            # Enhanced system message for code modifications
            system_message = """You are a helpful AI assistant that implements code changes in repositories.
Your task is to modify or create files to implement the requested changes.

When implementing code changes:
1. First identify which files need to be modified or created
2. For each file that needs changes:
   - If modifying an existing file, keep all existing functionality
   - If creating a new file, ensure it follows the project's patterns
3. You MUST return a JSON object with:
   - 'explanation': Detailed explanation of what changes you're making and why
   - 'changes': Dictionary where:
     - Keys are file paths relative to repository root
     - Values are the COMPLETE new content of those files
4. For any new endpoints:
   - Include proper error handling
   - Follow the project's existing patterns
   - Ensure all imports are correct
5. Include ALL necessary code - don't use placeholder comments

Example response format:
{
    "explanation": "Adding a new hello world endpoint to main.py",
    "changes": {
        "main.py": "complete updated file content here..."
    }
}"""

            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"""
Repository Content:
{code_contents}

Implementation Request: {prompt}

You MUST return a valid JSON object with 'explanation' and 'changes' fields as shown in the system message.
For any file you modify, you must include its complete content in the response."""}
            ]

            logger.debug(f"{self.name}: Sending request to OpenAI")
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=messages,
                temperature=0.2,
                max_tokens=2000
            )

            response_content = response.choices[0].message.content.strip()
            logger.debug(f"{self.name}: Received response from OpenAI: {response_content[:200]}...")
            
            try:
                # Try to parse response as JSON
                response_data = json.loads(response_content)
                
                # Validate response format
                if not isinstance(response_data, dict) or "changes" not in response_data or "explanation" not in response_data:
                    logger.error(f"{self.name}: Invalid response format - missing required fields")
                    raise ValueError("Response missing required fields")
                
                logger.info(f"{self.name}: Planning to modify files: {list(response_data['changes'].keys())}")
                logger.info(f"{self.name}: Change explanation: {response_data['explanation']}")
                
                # If we have changes and a repository path, apply them
                if response_data["changes"] and self.code_handler:
                    logger.info(f"{self.name}: Applying code changes to {len(response_data['changes'])} files")
                    change_results = self.code_handler.apply_changes(response_data["changes"])
                    
                    logger.info(f"{self.name}: Change results: {json.dumps(change_results, indent=2)}")
                    
                    # Add diff summary to response
                    if change_results["patches"]:
                        response_data["diff_summary"] = self.code_handler.get_diff_summary(
                            change_results["patches"]
                        )
                        logger.debug(f"{self.name}: Generated diff summary")
                    
                    response_data.update({
                        "change_results": change_results
                    })
                else:
                    logger.warning(f"{self.name}: No changes to apply or no code handler available")
                
                return {
                    "status": "success",
                    "response": response_data
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"{self.name}: Failed to parse GPT response as JSON: {str(e)}")
                logger.error(f"{self.name}: Raw response: {response_content}")
                return {
                    "status": "error",
                    "message": "GPT response was not valid JSON"
                }
            except ValueError as e:
                logger.error(f"{self.name}: Invalid response format: {str(e)}")
                return {
                    "status": "error",
                    "message": str(e)
                }
                
        except Exception as e:
            logger.error(f"{self.name}: Error during GPT processing - {str(e)}")
            return {"status": "error", "message": str(e)}

class AgentController:
    """Controls and orchestrates multiple agents"""
    def __init__(self):
        self.uploads_dir = Path("uploads")
        logger.debug("Agent Controller initialized")

        # Initialize agent selector
        self.agent_selector = AgentSelector()

        # Initialize agent instances
        self.agents = {
            "repository_analysis": lambda path: RepositoryAnalysisAgent(path),
            "code_reader": lambda path: CodeReaderAgent(path),
            "planner": lambda _: PlannerAgent(),
            "gpt": lambda _: GPTAgent()
        }

    def list_repositories(self) -> list:
        """List all available repositories in the uploads directory."""
        if not self.uploads_dir.exists():
            return []
        return [d.name for d in self.uploads_dir.iterdir() if d.is_dir()]

    def get_repository_path(self, repository_name: str) -> Optional[Path]:
        """Get the path to a specific repository."""
        repo_path = self.uploads_dir / repository_name
        return repo_path if repo_path.exists() else None
    
    def delete_repository(self, repository_name: str):
        """Delete a specific repository."""
        repo_path = self.uploads_dir / repository_name
        if repo_path.exists():
            shutil.rmtree(repo_path)
            logger.debug(f"Repository '{repository_name}' deleted")
        else:
            logger.error(f"Repository '{repository_name}' not found")

    async def process_repository_prompt(self, repository_name: str, prompt: str = None) -> Dict:
        """Orchestrate multiple agents to process a repository and optional prompt."""
        logger.debug(f"Starting repository processing for '{repository_name}'")

        repo_path = self.get_repository_path(repository_name)
        if not repo_path:
            logger.error(f"Repository '{repository_name}' not found")
            return {"status": "error", "message": f"Repository '{repository_name}' not found"}

        context = {}

        if prompt:
            # Get agent selection
            context["prompt"] = prompt
            selection_result = await self.agent_selector.process(context)
            if selection_result["status"] == "error":
                return selection_result

            selected_agents = selection_result["selected_agents"]
            logger.debug(f"Selected agents for processing: {selected_agents}")

            # Process with selected agents
            for agent_key in selected_agents:
                agent = self.agents[agent_key](repo_path if agent_key in ["repository_analysis", "code_reader"] else None)
                logger.debug(f"Running {agent.name}")

                result = await agent.process(context)
                if result["status"] == "error":
                    return result
                context.update(result)

            # Prepare response
            response = {
                "status": "success",
                "agent_selection": {
                    "agents_used": selected_agents,
                    "justification": selection_result["selection_justification"]
                }
            }

            # Add results from various agents if they were used
            if "results" in context:
                response["analysis"] = context["results"]
            if "plan" in context:
                response["plan"] = context["plan"]
            if "response" in context:
                response["gpt_response"] = context["response"]

            return response

        else:
            # If no prompt, just run repository analysis
            analysis_agent = self.agents["repository_analysis"](repo_path)
            result = await analysis_agent.process(context)
            if result["status"] == "error":
                return result

            return {
                "status": "success",
                "analysis": result["results"]
            }
