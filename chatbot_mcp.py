from langgraph.graph import StateGraph,START,END
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage,BaseMessage,AnyMessage,AIMessage,SystemMessage 
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode,tools_condition
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import asyncio
from typing import TypedDict,List,Literal,Annotated
import os 
from langchain_mcp_adapters.client import MultiServerMCPClient
load_dotenv()

groq_api_key=os.getenv("GROQ_API_KEY")
# print(groq_api_key)

llm=ChatGroq(model="llama-3.1-8b-instant",api_key=groq_api_key,temperature=0.5)

client = MultiServerMCPClient(
    {
        "arith": {
            "transport": "stdio",
            "command": "python",
            "args": ["C:\\Users\\rahul\\Downloads\\chatbot_ui agentic\\chatbot_new\\mcp_math_server.py"],
        }
        # "expense": {
        #     "transport": "streamable_http",  # if this fails, try "sse"
        #     "url": "https://splendid-gold-dingo.fastmcp.app/mcp"
        # }
    }
)





class ChatState(TypedDict):
    messages:Annotated[list[BaseMessage],add_messages]

async def build_graph():
    tools= await client.get_tools() # give all toool

    # print(tools)

    llm_with_bind_tool=llm.bind_tools(tools)

    async def chat_node(state:ChatState):
        messages=state["messages"]
        response=await llm_with_bind_tool.ainvoke(messages)
        return {"messages":[response]}
    
    tool_node= ToolNode(tools)


    graph=StateGraph(ChatState)
    graph.add_node("chat_node",chat_node)
    graph.add_node("tools",tool_node)

    graph.add_edge(START,"chat_node")
    graph.add_conditional_edges("chat_node",tools_condition)
    graph.add_edge("tools","chat_node")

    chatbot=graph.compile()
    
    return chatbot

async def main():
    

    chatbot=await build_graph()
    result=await chatbot.ainvoke({"messages":HumanMessage(content="Add 45 and 67 and give me the answer like a last-over thriller commentary." )})
    
    print(result['messages'][-1].content)


if __name__=="__main__":
    asyncio.run(main())