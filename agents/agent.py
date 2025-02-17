from pathlib import Path
from typing import Dict, Optional, List
import openai
from os import getenv
import os
import logging
import json

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class BaseAgent:
    """Base class for all agents"""
    def __init__(self, name: str):
        self.name = name
    
    async def process(self, context: Dict) -> Dict:
        """Process method to be implemented by specific agents"""
        raise NotImplementedError

class RepositoryAnalysisAgent(BaseAgent):
    def __init__(self, repository_path: Path):
        super().__init__("Repository Analysis Agent")
        self.repository_path = repository_path
        self.analysis_results = {}

    async def process(self, context: Dict) -> Dict:
        logger.debug(f"{self.name}: Starting repository analysis")
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
        code_extensions = {'.py', '.js', '.java', '.cpp', '.h', '.cs', '.php', '.rb', '.go', '.rs', 
                         '.ts', '.html', '.css', '.sql', '.md', '.json', '.yaml', '.yml'}
        
        try:
            for file_path in self.repository_path.rglob("*"):
                if file_path.is_file() and file_path.suffix in code_extensions:
                    if any(part in str(file_path) for part in ['venv', 'node_modules', '__pycache__', '.git']):
                        continue
                    
                    logger.debug(f"{self.name}: Reading file {file_path.relative_to(self.repository_path)}")
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
    def __init__(self):
        super().__init__("GPT Agent")
        openai.api_key = getenv("OPENAI_API_KEY")

    async def process(self, context: Dict) -> Dict:
        logger.debug(f"{self.name}: Starting GPT processing")
        try:
            code_contents = context.get("code_contents", "")
            prompt = context.get("prompt", "")
            plan = context.get("plan", "")
            
            # Enhanced system message with plan integration
            system_message = """You are a helpful AI assistant that analyzes code repositories and answers questions about them. 
Follow the provided analysis plan carefully and structure your response accordingly.
Include relevant code snippets when appropriate and explain your findings clearly."""

            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"""
Analysis Plan:
{plan}

Repository Content:
{code_contents}

User Question: {prompt}

Please provide a structured analysis following the plan above."""}
            ]
            
            logger.debug(f"{self.name}: Sending request to OpenAI")
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )
            
            logger.debug(f"{self.name}: Received response from OpenAI")
            return {
                "status": "success",
                "response": response.choices[0].message.content
            }
        except Exception as e:
            logger.error(f"{self.name}: Error during GPT processing - {str(e)}")
            return {"status": "error", "message": str(e)}

class AgentSelector(BaseAgent):
    """Determines which agents to use based on the prompt and context"""
    def __init__(self):
        super().__init__("Agent Selector")
        openai.api_key = getenv("OPENAI_API_KEY")
        
        # Define available agents and their capabilities
        self.available_agents = {
            "repository_analysis": {
                "name": "Repository Analysis Agent",
                "description": "Analyzes basic repository structure, counts files and directories, identifies file types",
                "use_cases": ["repository overview", "file statistics", "initial analysis"],
                "required_for": ["all queries"]  # This agent is always required as baseline
            },
            "code_reader": {
                "name": "Code Reader Agent",
                "description": "Reads and processes actual code content from files",
                "use_cases": ["code content analysis", "implementation details", "code understanding"],
                "required_for": ["code analysis", "implementation questions"]
            },
            "planner": {
                "name": "Planner Agent",
                "description": "Creates structured plans for detailed code analysis and modifications",
                "use_cases": ["code improvements", "architectural changes", "refactoring suggestions"],
                "required_for": ["code improvements", "architectural analysis"]
            },
            "gpt": {
                "name": "GPT Agent",
                "description": "Provides detailed analysis and responses based on code content",
                "use_cases": ["code explanation", "answering questions", "providing insights"],
                "required_for": ["all queries with prompt"]
            }
        }

    async def process(self, context: Dict) -> Dict:
        logger.debug(f"{self.name}: Starting agent selection process")
        try:
            prompt = context.get("prompt", "").lower()
            
            # Create selection prompt
            selection_prompt = f"""
Given the following user prompt and available agents, determine which agents should be used and in what order.

User Prompt: "{prompt}"

Available Agents:
{json.dumps(self.available_agents, indent=2)}

Consider that:
The Planner Agent is required for:
- Any code modifications or additions
- Complex code analysis
- Architectural changes
- Code improvements
- Feature additions

1. The Repository Analysis Agent is always required as a baseline
2. Not all agents are needed for every query
3. The Planner Agent is most useful for complex code analysis, improvements, or architectural questions
4. Simple questions about repository purpose or structure may not need the Planner
5. The Code Reader is needed whenever we need to analyze actual code content
6. The GPT Agent is needed whenever we need to provide a response to the user's prompt

Please provide:
1. List of required agents in order of execution
2. Brief justification for each agent's inclusion or exclusion

Respond in JSON format with 'selected_agents' (array of agent keys in order) and 'justification' (string).
"""
            
            logger.debug(f"{self.name}: Sending selection request to OpenAI")
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert in determining which tools are needed for code analysis tasks. Respond only in valid JSON format."},
                    {"role": "user", "content": selection_prompt}
                ],
                temperature=0.1  # Low temperature for more consistent responses
            )
            
            # Parse the response
            selection_result = json.loads(response.choices[0].message.content)
            logger.debug(f"{self.name}: Selected agents: {selection_result['selected_agents']}")
            
            return {
                "status": "success",
                "selected_agents": selection_result['selected_agents'],
                "selection_justification": selection_result['justification']
            }
            
        except Exception as e:
            logger.error(f"{self.name}: Error during agent selection - {str(e)}")
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
