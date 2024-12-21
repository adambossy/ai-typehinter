import os

import click
from dotenv import load_dotenv
from langchain.chat_models.base import BaseChatModel
from langchain.prompts import ChatPromptTemplate
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_community.chat_models import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langsmith import traceable, wrappers

load_dotenv()


class add_type_hints(BaseModel):
    """Response from type hint generation."""

    modified_source: str = Field(..., description="The type-hinted source code")
    error: str = Field("", description="Error message if type hinting failed")


class Conversation:
    def __init__(self, llm: BaseChatModel):
        """
        Initialize Conversation with any LangChain-compatible LLM.

        Args:
            llm: A LangChain chat model (ChatOpenAI, ChatAnthropic, etc.)
        """
        # Wrap the LLM for tracing based on its type
        if isinstance(llm, ChatOpenAI):
            self.llm = wrappers.wrap_openai(llm)
        elif isinstance(llm, ChatAnthropic):
            self.llm = wrappers.wrap_anthropic(llm)
        else:
            self.llm = llm  # Fallback for other LLM types

        # Bind the type hint tool to the LLM
        self.llm = self.llm.bind_tools([add_type_hints], tool_choice="add_type_hints")

        # Define the system prompt
        self.system_prompt = """You are a helpful AI assistant focused on adding type hints to Python code.
When asked to add type hints to a function:
1. Consider the provided context about calling and called functions
2. Analyze the function's parameters and return values
3. Add appropriate Python 3.9+ type hints while preserving all existing functionality
   - Use built-in types like list[str] instead of List[str]
   - Use | for union types instead of Union (e.g., str | None)
   - Use dict[str, str | bool] instead of Dict[str, Union[str, bool]]
4. Keep all docstrings and comments intact
5. Return only the type-hinted version of the function"""

        # Create the conversation chain with example
        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.system_prompt),
                HumanMessage(
                    content="""Add type hints to this function:

Function Context:
Called by functions:
- ShoppingCart.checkout
- Order.validate

Calls these functions:
- Database.query
- Validator.check_amount

def get_user_data(username):
    '''Fetch user data from database'''
    return {"name": username, "active": True}"""
                ),
                AIMessage(
                    content="""def get_user_data(username: str) -> dict[str, str | bool]:
    '''Fetch user data from database'''
    return {"name": username, "active": True}"""
                ),
                MessagesPlaceholder(variable_name="input"),
            ]
        )

        # Create chain without itemgetter
        self.chain = self.prompt | self.llm

    @traceable
    def completion(self, prompt: str) -> str:
        """
        Get a completion from the LLM.

        Args:
            prompt: The input prompt requesting type hints

        Returns:
            The type-hinted version of the function
        """
        response = self.chain.invoke({"input": [HumanMessage(content=prompt)]})
        return response.tool_calls[0]["args"]


MODELS = {
    "gpt-4o": lambda: ChatOpenAI(
        model="gpt-4o", temperature=0.1, api_key=os.getenv("OPENAI_API_KEY")
    ),
    "claude": lambda: ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        temperature=0.1,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    ),
}

DEFAULT_PROMPT = """Add type hints to this function:
def process_data(data):
    '''Process the input data'''
    result = []
    for item in data:
        result.append(item * 2)
    return result"""


@click.command()
@click.option(
    "--model",
    type=click.Choice(["gpt-4o", "claude"]),
    default="claude",
    help="The LLM model to use",
)
@click.option("--prompt", default=DEFAULT_PROMPT, help="The prompt to send to the LLM")
def cli(model: str, prompt: str) -> None:
    """CLI tool for getting type hints from an LLM."""
    llm = MODELS[model]()
    conversation = Conversation(llm)

    click.echo("\nInput function:")
    click.echo(
        prompt.split("Add type hints to this function:\n")[1]
    )  # Extract just the function part
    click.echo("\nType-hinted version:")
    result = conversation.completion(prompt)
    click.echo(result)


if __name__ == "__main__":
    cli()
