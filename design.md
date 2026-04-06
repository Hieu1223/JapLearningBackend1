# DB
## Objects

* User

    * OAUTH

* Transcript

    * Data
    * Source Video URL
    * Title
    * Thumbnail
    * Status Failed | Pending | Sucess
    * Public

* Card

* Deck

    * Public Decks

    * Private Decks

* Conversation

    * Content

    * 

## Relations

* user's transcript history
* user's deck



# Draft
## Flashcard
* Review Flash card

    * Show the review time according to the level
    * Allows undo
    * Allows bury
    * Allows reviewing according to the word types
        * Noun
        * Verb Noun
        * ...

* Import from anki

    * Use AI to read the template and to determine the field to extract for front and back

* Tokenize text

    * Use sudachi to tokenize text

    * Create flashcard card from selection

* Transcribe youtube video

    * Transcribe video
    
    * Create flashcard from selected tokens

# API
## Transcription 

1. Request
    
    * Youtube link

2. Response

    * Transcript

    * Words timestamp




# Use case

## Actors

* User 

* Transcript Server

## Usecase 1 **Review Flash card**
## Usecase 2 **CUD Flash card**
## Usecase 3 **Transcribe Youtube Video**


### Basic flow

1. Client shows youtube frontend with newpipe extractor
1. User browses youtube
2. Send videos to check transcription status
2. User click video
3. User click the trancribe button


2. Client software check if a video is being processed or already processed,  
3. Client software download video, turn into audio and process
4. Client software send audio
5. Backend returns transcript id
5. Backend mark the audio as being in queue
5. Backend put into a queue
6. Back end mark the audio as being transcripted
7. Backend transcribe the file
8. Backend retreive the data
9. Backend update the content
10. Backend mark the audio as finished 
### Alternative flow
1. Video is being processed or already processed
    1. Backend returns the transcription id used for lookup
    2. End
2. Video 

## Usecase 4 **Transcribe uploaded video**



## Usecase 4 **See transcribed video**

### Basic flow

1. User click video card
2. Backend retreives transcript data
3. User load a portion of the data



## Usecase 5 **Conversation**
## Usecase 6 **Look up words with AI**
## Usecase 7 **Tokenize Text**
## Usecase 8 **Explain with AI**



## Usecase 9 **Add AI explanation to Flashcard**
## Usecase 10 **Sentence fixer**

User put in a sentence in japanese, the ai will try guess the sentence

Choose the meaning and have the ai fix

Can choose desired skill level

Save the sentence for later review, use the spaced repetition

## Usecase 10 **Import Anki**

## Usecase 11 **Export to Anki**

## Usecase 12 **Quick create deck**

## Usecase 13 **Browse public decks**

## Usecase 14 **Browse public transcript**
