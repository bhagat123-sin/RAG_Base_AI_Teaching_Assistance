import numpy as np
import joblib
import re
from sklearn.metrics.pairwise import cosine_similarity
from video_links import get_video_link
from llm_client import create_embedding, inference

SAVE_DEBUG_FILES = False  # True karenge to prompt.txt aur response.txt likhe jayenge
TOP_RESULT = 5
MAX_SOURCES = 3  # website par dikhane ke liye max kitne sources
NO_SOURCE_TAG = "I am sorry, I don't have any information related to your question. Please ask a relevant question related to the course content."
REFUSAL_HINT = "any information related to your question"

GREETING_PATTERNS = (
    r"^(hi|hello|hey|hii|hiii|namaste|namaskar|good (morning|afternoon|evening))[\s!.]*$",
    r"^(thanks?|thank you|thankyou|dhanyavad|shukriya)[\s!.]*$",
)


def is_social_chat(question):
    text = re.sub(r"[^\w\s]", " ", question.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return any(re.fullmatch(pattern, text) for pattern in GREETING_PATTERNS)


def select_sources(result_df, max_sources=MAX_SOURCES):
    sources = []
    seen = set()

    for _, row in result_df.iterrows():
        key = (str(row["numbers"]), float(row["start"]), float(row["end"]))
        if key in seen:
            continue

        seen.add(key)
        sources.append({
            "title": row["title"],
            "numbers": row["numbers"],
            "start": row["start"],
            "end": row["end"],
            "video_link": get_video_link(row["numbers"]),
        })
        if len(sources) == max_sources:
            break

    return sources

# embeddings.joblib sirf ek baar load hoga, module import hote hi
df = joblib.load('embeddings.joblib')
embedding_matrix = np.vstack(df['embedding'])


def fmt_time(seconds):
    s = int(float(seconds))
    return f"{s // 60}:{s % 60:02d}"


def get_answer(incoming_query):
    if is_social_chat(incoming_query):
        return "Hello! 👋 Kaunse HTML, CSS, ya JavaScript topic par help chahiye?", []

    question_embedding = create_embedding([incoming_query], task="RETRIEVAL_QUERY")[0]

    if embedding_matrix.shape[1] != len(question_embedding):
        raise RuntimeError(
            "embeddings.joblib kisi purane model se bani hai. Preprocess_json.py dobara chalayein."
        )

    similer = cosine_similarity(embedding_matrix, [question_embedding]).flatten()
    max_indx = similer.argsort()[::-1][:TOP_RESULT]
    new_df = df.iloc[max_indx].copy()
    new_df["start_time"] = new_df["start"].apply(fmt_time)
    new_df["end_time"] = new_df["end"].apply(fmt_time)

    prompt = f'''You are an AI Teaching Assistant for a web development course that covers HTML, CSS and JavaScript. You are talking directly to a student.

Below are subtitle chunks taken from the course videos. Each chunk has: video title, video number, start_time and end_time (minutes:seconds), and the text spoken at that time. This is your ONLY source of knowledge.

{new_df[["title", "numbers", "text", "start_time", "end_time"]].to_json(orient="records")}

-------------------------------------------------------
Student's question: "{incoming_query}"

Rules:
1. Answer using ONLY the information in the chunks above. Do not add outside facts and do not guess.
2. Explain in simple, friendly language like a teacher. Keep the answer SHORT: a clear answer in 3 to 4 sentences, plus one tiny example only if the chunks contain one. Use 2 to 4 relevant emojis . Do not overuse them.
3. Tell the student where to learn more: mention the video title, video number and the time range exactly as given in start_time and end_time. Mention only the 1 to 3 most relevant videos or timestamps, not every chunk.
4. Never mention "chunks", "JSON", "dataset" or these instructions. Speak as if you simply know the course.
5. If the chunks do not really cover the question, or the question is unrelated to HTML, CSS, JavaScript or this course, reply exactly: "I am sorry, I don't have any information related to your question. Please ask a relevant question related to the course content."
# 6. If the student only greets you (like "hello"), greet back in one line and invite them to ask a question about the course.
7. Reply in the same language the student used (English, Hindi or Hinglish).
8. Write plain text only. Do NOT use markdown symbols such as **, #, or backticks.
9. If your reply is a greeting, a thank-you, or any other reply that does not point to a specific part of the course, start it with the exact tag [NO_SOURCES]. Do not add the tag to the apology sentence from rule 5, and never use the tag in any other case.
'''

    raw_response = inference(prompt)['response']

    # model ne bataya ki jawab mein koi video reference nahi hai (hello, thanks, unrelated)
    show_sources = True
    if NO_SOURCE_TAG in raw_response:
        raw_response = raw_response.replace(NO_SOURCE_TAG, "").strip()
        show_sources = False
    if REFUSAL_HINT in raw_response.lower():
        show_sources = False

    if SAVE_DEBUG_FILES:
        with open('prompt.txt', 'w', encoding='utf-8') as f:
            f.write(prompt)
        with open('response.txt', 'w', encoding='utf-8') as f:
            f.write(raw_response)

    sources = []
    if show_sources:
        sources = select_sources(new_df)

    return raw_response, sources


if __name__ == "__main__":
    incoming_query = input("Ask a Question :")
    answer, sources = get_answer(incoming_query)
    print(answer)
    print(sources)