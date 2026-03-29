from langchain_core.prompts import PromptTemplate
from  langgraph.graph.state import StateGraph,START,END
from langgraph.prebuilt import ToolNode,tools_condition
from langgraph.graph.message import BaseMessage,add_messages
from langchain_core.messages import AnyMessage,AIMessage,HumanMessage
import requests
from langchain_groq import ChatGroq
from langgraph.types import interrupt,Command
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from typing import TypedDict,Annotated
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

groq_api_key=os.getenv('GROQ_API_KEY')
print(groq_api_key)

llm=ChatGroq(model="qwen/qwen3-32b",temperature=0.2,api_key=groq_api_key)

@tool
def get_stock_price(symbol:str)->dict:
    """
    Fetch the stock price of company with give symbol e.g(AAPL,SAM)
    using the api key and url
    """

    url="https://www.alphavantage.co/query"f"?function=GLOBAL_QUOTE&symbol={symbol}&apikey=C9PE94QUEW9VWGFM"

    response=requests.get(url)

    return response.json()

@tool
def purchase_stock(symbol:str,quantity:int)->dict:
    """
    Simulate purchasing a given quantity of a stock symbol.

    HUMAN-IN-THE-LOOP:
    Before confirming the purchase, this tool will interrupt
    and wait for a human decision ("yes" / anything else)"""

    decision=interrupt(f"Approved the {quantity} stock of  {symbol} in (yes/no)")

    if isinstance(decision,str) and decision.lower() == "yes":
        return {
            "status":"success",
            "message":f"Purchase order placed for {quantity} shares of {symbol}.",
            "symbol":symbol,
            "quantity":quantity
        }
    else:
        return {
            "status":"rejected",
            "message":f"Your {quantity} stock has been rejected of {symbol}",
            "symbol":symbol,
            "quantity":quantity
        }
    
tools=[get_stock_price,purchase_stock]

llm_with_tool=llm.bind_tools(tools)

class Chatstate(TypedDict):
    messages:Annotated[list[BaseMessage],add_messages]

graph=StateGraph(Chatstate)

def chat_node(state:Chatstate):
    """LLM node that may answer or request a tool call."""

    messages=state['messages']
    response=llm_with_tool.invoke(messages)

    return {
        "messages":[response]
    }

tool_node=ToolNode(tools)
graph.add_node("chat_node",chat_node)
graph.add_node("tools",tool_node)

graph.add_edge(START,"chat_node")
graph.add_conditional_edges("chat_node",tools_condition)
graph.add_edge("tools","chat_node")
checkpointer=MemorySaver()

chatbot=graph.compile(checkpointer=checkpointer)

if __name__=="__main__":

    thread_id="demo_thread"

    while(True):
        user_input=input("You:")
        if user_input.strip().lower() in {"exit","bye"}:
            print('Goodbye..')
            break

        state={"messages":[HumanMessage(content=user_input)]}

        result=chatbot.invoke(
            state,
            config={"configurable":{"thread_id":thread_id}}
        )

        interrupts=result.get("__interrupt__", [])

        if interrupts:

            prompt_to_human=interrupts[0].value
            print(f"HITL:{prompt_to_human}")
            decision=input("Your decision:").strip().lower()

            result=chatbot.invoke(
                Command(resume=decision),
                config={"configurable":{"thread_id":thread_id}}
            )
        messages=result['messages']
        last_msg=messages[-1]

        print(f"Ai:{last_msg.content}\n")





