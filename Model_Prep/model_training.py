import os
import random
import json
import pickle
import numpy as np
import nltk
from nltk.stem import WordNetLemmatizer
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Activation, Dropout
from tensorflow.keras.optimizers import SGD
from tensorflow.keras import regularizers  # Import regularizer for weight decay

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # Disable GPU

# Initialize Lemmatizer
lemmatizer = WordNetLemmatizer()

# Load intents from the JSON file
intents = json.load(open('intents.json'))

words = []
classes = []
documents = []
ignore_letters = ['?', '!', '.', ',']

# Tokenize each pattern in the intents and build words and classes
for intent in intents['intents']:
    for pattern in intent['patterns']:
        word_list = nltk.word_tokenize(pattern)
        words.extend(word_list)
        documents.append((word_list, intent['tag']))
        if intent['tag'] not in classes:
            classes.append(intent['tag'])

# Lemmatize words and remove ignore letters
words = [lemmatizer.lemmatize(word) for word in words if word not in ignore_letters]
words = sorted(set(words))  # Remove duplicates and sort words

classes = sorted(set(classes))  # Sort classes

# Ensure 'model' directory exists
if not os.path.exists('model'):
    os.makedirs('model')

# Save words and classes to pickle files
pickle.dump(words, open('model/words.pkl', 'wb'))
pickle.dump(classes, open('model/classes.pkl', 'wb'))

# Prepare training data
training = []
output_empty = [0] * len(classes)

# Create bag of words and output row (one-hot encoded) for each document
for document in documents:
    bag = []
    word_patterns = document[0]
    word_patterns = [lemmatizer.lemmatize(word.lower()) for word in word_patterns]

    # Create a bag of words
    for word in words:
        bag.append(1) if word in word_patterns else bag.append(0)

    output_row = list(output_empty)
    output_row[classes.index(document[1])] = 1

    # Debugging: Check lengths of 'bag' and 'output_row'
    if len(bag) != len(words):
        print(f"Warning: Bag length mismatch at: {document}")
    if len(output_row) != len(classes):
        print(f"Warning: Output row length mismatch at: {document}")

    # Append to training data
    training.append([bag, output_row])

# Debugging: Check training data structure
print(f"Total training samples: {len(training)}")
print(f"Example training data: {training[0]}")

# Ensure consistent lengths for 'bag' and 'output_row'
if len(training) > 0:
    bag_len = len(training[0][0])  # Length of the 'bag'
    output_row_len = len(training[0][1])  # Length of the 'output_row'

    assert all(len(item[0]) == bag_len and len(item[1]) == output_row_len for item in training), \
        "Inconsistent lengths in training data"

# Convert training data to numpy array
try:
    training = np.array(training)
    print("Successfully converted to numpy array")
except ValueError as e:
    print(f"Error converting to numpy array: {e}")
    for i, sample in enumerate(training):
        print(f"Training sample {i}: {sample[0]} (bag), {sample[1]} (output_row)")

# Now that `training` is a NumPy array, we can split the input and output data
train_x = np.array([item[0] for item in training])  # Extract the bags of words
train_y = np.array([item[1] for item in training])  # Extract the output rows

# Define the model architecture
model = Sequential()

# Add layers with L2 regularization (for weight decay)
model.add(Dense(128, input_shape=(len(train_x[0]),), activation='relu', kernel_regularizer=regularizers.l2(1e-6)))
model.add(Dropout(0.5))
model.add(Dense(64, activation='relu', kernel_regularizer=regularizers.l2(1e-6)))
model.add(Dropout(0.5))
model.add(Dense(len(train_y[0]), activation='softmax'))

# Compile the model using SGD (no weight_decay parameter)
sgd = SGD(learning_rate=0.01, momentum=0.9, nesterov=True)

model.compile(loss='categorical_crossentropy', optimizer=sgd, metrics=['accuracy'])

# Train the model
model.fit(np.array(train_x), np.array(train_y), epochs=200, batch_size=5, verbose=1)

# Save the trained model
model.save('model/chatbot_model.keras')
