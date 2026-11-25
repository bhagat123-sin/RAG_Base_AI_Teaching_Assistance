# Project Description: RAG-Based AI Teaching Assistant

The **RAG-Based AI Teaching Assistant** is an AI-powered system designed to help students understand and search information from recorded video lectures. The main purpose of this project is to make learning easier by allowing students to ask questions about lecture content and receive relevant answers without watching the entire video again.

The system uses **FFmpeg** to extract audio from video lectures and **OpenAI Whisper** to convert speech into text. The generated transcripts are then cleaned, divided into smaller chunks, and converted into vector embeddings using an embedding model. These embeddings are stored in a vector database or search index for efficient retrieval.

When a student enters a question, the system converts the query into an embedding and retrieves the most relevant information from the lecture transcripts. This retrieved information is passed to a Large Language Model (LLM) through **Ollama**, which generates a context-based answer.

* Technologies Used
- **Python:** Core programming language.
- **FFmpeg:** Audio extraction from video lectures.
- **Whisper:** Speech-to-text transcription.
- **Embedding Model:** Converts text into numerical vectors.
- **Chroma / FAISS:** Vector storage and similarity search (as applicable to the implementation).
- **Ollama:** Runs the Large Language Model.
- **RAG:** Combines information retrieval and AI-generated responses.

* Main Objective
To develop an intelligent teaching assistant that allows students to interact with recorded lectures through natural-language questions and receive answers based on the lecture content.

* Expected Outcome
The project aims to save students' time, improve access to educational content, and provide an easier way to revise concepts from recorded video lectures.
