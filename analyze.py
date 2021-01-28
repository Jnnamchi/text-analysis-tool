from random_username.generate import generate_username
from nltk.tokenize import word_tokenize, sent_tokenize

# Welcome User
def welcomeUser():
	print("\nWelcome to the text analysis tool, I will mine and analyze a body of text from a file you give me!")

# Get Username
def getUsername():

	maxAttempts = 3
	attempts = 0

	while attempts < maxAttempts:

		# Print message prompting user to input their name
		inputPrompt = ""
		if attempts == 0:
			inputPrompt = "\nTo begin, please enter your username:\n"
		else:
			inputPrompt = "\nPlease try again:\n"
		usernameFromInput = input(inputPrompt)

		# Validate username
		if len(usernameFromInput) < 5 or not usernameFromInput.isidentifier():
			print("Your username must be at least 5 characters long, alphanumeric only (a-z/A-Z/0-9), have no spaces, and cannot start with a number!")
		else:
			return usernameFromInput

		attempts += 1

	print("\nExhausted all " + str(maxAttempts) + " attempts, assigning username instead...")
	return generate_username()[0]

# Greet the user
def greetUser(name):
	print("Hello, " + name)

# Get text from file
def getArticleText():
	f = open("files/article.txt", "r")
	rawText = f.read()
	f.close()
	return rawText.replace("\n", " ").replace("\r", "")

# Extract Sentences from raw Text Body
def tokenizeSentences(rawText):
	return sent_tokenize(rawText)

# Extract Words from list of Sentences
def tokenizeWords(sentences):
	words = []
	for sentence in sentences:
		words.extend(word_tokenize(sentence))
	return words

# Get User Details
welcomeUser()
username = getUsername()
greetUser(username)

# Extract and Tokenize Text
articleTextRaw = getArticleText()
articleSentences = tokenizeSentences(articleTextRaw)
articleWords = tokenizeWords(articleSentences)

# Print for testing
print("GOT:")
print(articleWords)