import random
import json
import pickle
import numpy as np
import nltk
from nltk.stem import WordNetLemmatizer
from tensorflow.keras.models import load_model

# Initialize Lemmatizer
lemmatizer = WordNetLemmatizer()

# Load intents file
intents = json.load(open('intents.json'))

# Load preprocessed data (words, classes) and trained model
words = pickle.load(open('model/words.pkl', 'rb'))
classes = pickle.load(open('model/classes.pkl', 'rb'))
model = load_model('model/chatbot_model.keras')


def clean_up_sentence(sentence):
    """Tokenizes and lemmatizes the input sentence"""
    sentence_words = nltk.word_tokenize(sentence)
    sentence_words = [lemmatizer.lemmatize(word.lower()) for word in sentence_words]  # Ensure lowercasing
    return sentence_words


def bag_of_words(sentence):
    """Converts a sentence into a bag of words vector"""
    sentence_words = clean_up_sentence(sentence)
    bag = [0] * len(words)
    for w in sentence_words:
        for i, word in enumerate(words):
            if word == w:
                bag[i] = 1
    return np.array(bag)


def predict_class(sentence):
    """Predicts the class (intent) of the sentence"""
    bow = bag_of_words(sentence)
    res = model.predict(np.array([bow]))[0]
    ERROR_THRESHOLD = 0.25

    # Filter predictions based on threshold
    results = [[i, r] for i, r in enumerate(res) if r > ERROR_THRESHOLD]
    results.sort(key=lambda x: x[1], reverse=True)

    return_list = []
    for r in results:
        return_list.append({'intent': classes[r[0]], 'probability': str(r[1])})

    return return_list


def get_response(intents_list, intents_json):
    """Returns a response based on the predicted intent"""
    tag = intents_list[0]['intent']
    list_of_intents = intents_json['intents']

    # Find the matching intent and return a random response
    for i in list_of_intents:
        if i['tag'] == tag:
            result = random.choice(i['responses'])
            break
    return result

print(f"Uok Bot: Before we proceed, I want to make sure we have your consent to \n"
        f"\t\tcollect and process your personal information in accordance with POPI \n"
        f"\t\t(Protection of Personal Information) regulations. Continuing interaction \n"
        f"\t\twith this platform will be deemed as consent. We will only use your information \n"
        f"\t\tconfor the purpose of improving our services and ensuring a better user experience.\n"
        f"Uok Bot: Continue? or exit")
while True:

    # print(f"Uok Bot: Continue? or exit")
    message = input("You: ")
    # print(f"Uok Bot: May I have your name?")
    ints = predict_class(message)
    res = get_response(ints, intents)
    print(f"Uok Bot: {res}")



  

