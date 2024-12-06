import os

import click
from dotenv import load_dotenv
from langchain.chains import LLMChain
from langchain.chat_models.base import BaseChatModel
from langchain.prompts import ChatPromptTemplate
from langchain.schema import AIMessage, HumanMessage
from langchain_community.chat_models import ChatAnthropic
from langchain_openai import ChatOpenAI

load_dotenv()


class Conversation:
    def __init__(self, llm: BaseChatModel):
        """
        Initialize Conversation with any LangChain-compatible LLM.

        Args:
            llm: A LangChain chat model (ChatOpenAI, ChatAnthropic, etc.)
        """
        self.llm = llm

        # Define the system prompt
        self.system_prompt = """You are a helpful AI assistant focused on adding type hints to Python code.
When asked to add type hints to a function:
1. Analyze the function's parameters and return values
2. Add appropriate Python 3.9+ type hints while preserving all existing functionality
   - Use built-in types like list[str] instead of List[str]
   - Use | for union types instead of Union (e.g., str | None)
   - Use dict[str, str | bool] instead of Dict[str, Union[str, bool]]
3. Keep all docstrings and comments intact
4. Return only the type-hinted version of the function"""

        # Define one-shot example for few-shot learning
        self.example_conversation = [
            HumanMessage(
                content="""Add type hints to this function:
def get_user_data(username):
    '''Fetch user data from database'''
    return {"name": username, "active": True}"""
            ),
            AIMessage(
                content="""def get_user_data(username: str) -> dict[str, str | bool]:
    '''Fetch user data from database'''
    return {"name": username, "active": True}"""
            ),
        ]

        # Create the conversation chain
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                self.example_conversation[0],  # HumanMessage
                self.example_conversation[1],  # AIMessage
                ("human", "{input}"),
            ]
        )

        # Create chain without itemgetter
        self.chain = self.prompt | llm

    def completion(self, prompt: str) -> str:
        """
        Get a completion from the LLM.

        Args:
            prompt: The input prompt requesting type hints

        Returns:
            The type-hinted version of the function
        """
        response = self.chain.invoke({"input": prompt})
        return response.content


MODELS = {
    "gpt-4": lambda: ChatOpenAI(
        model="gpt-4", temperature=0.1, api_key=os.getenv("OPENAI_API_KEY")
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
    type=click.Choice(["gpt-4", "claude"]),
    default="claude",
    help="The LLM model to use",
)
@click.option("--prompt", default=DEFAULT_PROMPT, help="The prompt to send to the LLM")
def cli(model: str, prompt: str) -> None:
    """CLI tool for getting type hints from an LLM."""
    llm = MODELS[model]()
    conversation = Conversation(llm)

    result = conversation.completion(prompt)
    click.echo(result)


if __name__ == "__main__":
    cli()
