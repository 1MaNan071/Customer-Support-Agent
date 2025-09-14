import os
from dotenv import load_dotenv
load_dotenv()

from typing import List, Literal, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from contextlib import ExitStack
_stack = ExitStack()

from langgraph.checkpoint.sqlite import SqliteSaver


from faq_data import faqs


class GraphState(TypedDict):
    messages: List[BaseMessage]
    classification: str


faq_texts = [
    f"Question: {item['question']}\nAnswer: {item['answer']}"
    for item in faqs
]
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = FAISS.from_texts(faq_texts, embedding=embeddings)
retriever = vectorstore.as_retriever()


class RouteQuery(BaseModel):
    datasource: Literal["faq_retriever", "escalate_harmful", "escalate_off_topic"] = Field(...,)


def classify_input_node(state: GraphState):

    print("---NODE: CLASSIFYING INPUT---")

    user_input = state["messages"][-1].content

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

    structured_llm = llm.with_structured_output(RouteQuery)

    system_prompt = """You are a routing agent for a customer support assistant. Classify the user's query to the correct path.
- 'faq_retriever': For standard support questions.
- 'escalate_harmful': For queries with PII, abuse, or security risks.
- 'escalate_off_topic': For off-topic chit-chat."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_input)
    ])
    router_result = (prompt | structured_llm).invoke({"input": user_input})
    print(f"Routing decision: {router_result.datasource}")
    return {"classification": router_result.datasource}

def answer_faq_node(state: GraphState):
    print("---NODE: ANSWERING FROM FAQ---")
    user_input = state["messages"][-1].content
    context_docs = retriever.invoke(user_input)
    context_str = "\n\n".join([doc.page_content for doc in context_docs])

    prompt = f"""
You are a helpful customer support assistant.
Use ONLY the following context to answer the question.
If the answer is not in the context, say "I'm not sure about that."

Context:
{context_str}

Question: {user_input}
Answer:
""".strip()

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)
    response = llm.invoke(prompt)
    return {"messages": [AIMessage(content=response.content.strip())]}

def escalate_harmful_node(state: GraphState):
    print("---NODE: ESCALATING HARMFUL/PII QUERY---")
    response_text = "I cannot process this request due to safety policies. Please avoid sharing personal information. How else can I help you?"
    return {"messages": [AIMessage(content=response_text)]}

def escalate_off_topic_node(state: GraphState):
    print("---NODE: ESCALATING OFF-TOPIC QUERY---")
    response_text = "I am a customer support assistant. I can help with questions about our products and services."
    return {"messages": [AIMessage(content=response_text)]}


def router_edge(state: GraphState):
    val = state.get("classification")
    return [val] if val is not None else []


def compile_graph():
    workflow = StateGraph(GraphState)
    workflow.add_node("classify_input", classify_input_node)
    workflow.add_node("faq_retriever", answer_faq_node)
    workflow.add_node("escalate_harmful", escalate_harmful_node)
    workflow.add_node("escalate_off_topic", escalate_off_topic_node)

    workflow.set_entry_point("classify_input")

    workflow.add_conditional_edges(
        "classify_input",
        router_edge,
        {
            "faq_retriever": "faq_retriever",
            "escalate_harmful": "escalate_harmful",
            "escalate_off_topic": "escalate_off_topic",
        },
    )
    workflow.add_edge("faq_retriever", END)
    workflow.add_edge("escalate_harmful", END)
    workflow.add_edge("escalate_off_topic", END)

    memory = _stack.enter_context(SqliteSaver.from_conn_string("conversations.sqlite"))
    return workflow.compile(checkpointer=memory)


app = compile_graph()
