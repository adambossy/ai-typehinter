from langchain.chains import LLMChain
from langchain.chat_models.base import BaseChatModel
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import AIMessage, HumanMessage


class Conversation:
    def __init__(self, llm: BaseChatModel):
        """
        Initialize Conversation with any LangChain-compatible LLM.

        Args:
            llm: A LangChain chat model (ChatOpenAI, ChatAnthropic, etc.)
        """
        self.llm = llm
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )

        # Define the system prompt
        self.system_prompt = """You are a helpful AI assistant focused on adding type hints to Python code.
When asked to add type hints to a function:
1. Analyze the function's parameters and return values
2. Add appropriate type hints while preserving all existing functionality
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
                content="""def get_user_data(username: str) -> Dict[str, Union[str, bool]]:
    '''Fetch user data from database'''
    return {"name": username, "active": True}"""
            ),
        ]

        # Create the conversation chain
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="examples"),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )

        self.chain = LLMChain(
            llm=self.llm, prompt=self.prompt, memory=self.memory, verbose=False
        )

        self.initialize_conversation()

    def initialize_conversation(self) -> None:
        """Initialize conversation with example messages"""
        self.memory.clear()
        for message in self.example_conversation:
            self.memory.chat_memory.add_message(message)

    def completion(self, prompt: str) -> str:
        """
        Get a completion from the LLM.

        Args:
            prompt: The input prompt requesting type hints

        Returns:
            The type-hinted version of the function
        """
        response = self.chain.invoke(
            {"input": prompt, "examples": self.example_conversation}
        )
        return response["text"]

    def reset_conversation(self) -> None:
        """Reset the conversation to initial state"""
        self.initialize_conversation()
