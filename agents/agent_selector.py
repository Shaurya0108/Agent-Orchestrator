import json
from typing import Dict
from dotenv import load_dotenv
from os import getenv
import logging
import openai
from agents.base_agent import BaseAgent

load_dotenv()

logger = logging.getLogger(__name__)

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

Consider these STRICT rules for agent selection:
1. The Repository Analysis Agent is ALWAYS required first as a baseline
2. The Code Reader Agent is ALWAYS required when we need to analyze or modify code
3. The Planner Agent is REQUIRED for ANY of these cases:
   - Adding new code or endpoints
   - Modifying existing code
   - Making any code changes
   - Adding new features
   - Code improvements
   - Architectural changes
4. The GPT Agent is ALWAYS required last when we need to provide a response

For prompts requesting code changes (like "add endpoint", "create function", "implement feature"):
- MUST include Planner Agent
- Order should be: repository_analysis -> code_reader -> planner -> gpt

Provide:
1. List of required agents in order of execution
2. Brief justification for each agent's inclusion

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
            # logger.debug(f"{self.name}: Selected agents: {selection_result['selected_agents']}")

            return {
                "status": "success",
                "selected_agents": selection_result['selected_agents'],
                "selection_justification": selection_result['justification']
            }

        except Exception as e:
            logger.error(f"{self.name}: Error during agent selection - {str(e)}")
            return {"status": "error", "message": str(e)}
