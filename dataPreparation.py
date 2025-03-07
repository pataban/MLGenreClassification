import nltk
import json
import string
import numpy as np
import pandas as pd
import tensorflow as tf
from itertools import chain
from keras.utils import pad_sequences
from sklearn.preprocessing import StandardScaler

from constants import *
from support import *


def loadRawBooksData(verbose=False):
    books = pd.read_csv(DATA_DIR_PATH + RAW_BOOKS_DATA_FILE_NAME, sep='\t')
    books.columns = ('wId', 'fId', 'title',
                     'author', 'date', 'genres', 'summary')

    books = books.drop(
        columns=['wId', 'fId', 'title', 'author', 'author', 'date']).dropna()

    books['genres'] = books['genres'].map(
        lambda genres: list(json.loads(genres).values()))

    if verbose > 1:
        print('raw data:\n', books)
        print('\nraw data info:')
        books.info()
    return books


def loadRawMoviesData(verbose=0):
    movies=pd.concat([pd.read_csv(DATA_DIR_PATH + RAW_MOVIES_DATA_FILE_NAME[0],
                          sep=' ::: ',header=None,engine='python'),
                     pd.read_csv(DATA_DIR_PATH + RAW_MOVIES_DATA_FILE_NAME[1],
                                 sep=' ::: ',header=None,engine='python')])

    movies.columns = ('id', 'title', 'genre', 'summary')
    movies = movies.drop(columns=['id', 'title']).dropna()

    if verbose > 1:
        print('raw data:\n', movies)
        print('\nraw data info:')
        movies.info()
    return movies


def printLen(summaries):
    lens = list(map(len, summaries))
    print('Min = %d Avg = %.2f Max = %d' %
          (min(lens), sum(lens)/len(lens), max(lens)))


def countElements(elements, top=None):
    count = {}
    for e in elements:
        if e in count:
            count[e] += 1
        else:
            count[e] = 1

    count = list(count.items())
    count.sort(key=lambda gc: gc[1], reverse=True)
    if top is not None:
        count = count[0:top]
    return count


def select(books, selection=None, unique=False):
    genres = []
    summaries = []
    for (genre, summary) in zip(books['genres'], books['summary']):
        if (((not unique) or (len(genre) == 1)) and
                ((selection is None) or (len(set(genre).intersection(selection)) > 0))):
            genres.append(genre[0]if unique else list(
                set(genre).intersection(selection)))
            summaries.append(summary)
    return {'genres': genres, 'summary': summaries}


def selectData(books, verbose=False):
    if verbose > 1:
        print('\nfullGenreCount:\n', countElements(books['genres'].sum(), 10))

    books = select(books, selection=GENRE_INDEX.keys())
    if verbose > 1:
        print('\nselectedGenreCount: All =', len(books['genres']), '\n',
              countElements(chain.from_iterable(books['genres'])))

    books = select(books, unique=True)
    if verbose > 1:
        print('\nuniqueGenreCount: All =', len(books['genres']), '\n',
              countElements(books['genres']))
        print('\ncharacters:')
        printLen(books['summary'])

    return (books['genres'], books['summary'])


def cleanSummaryManual(summary):
    cSummary = ''
    for c in summary:
        if c.isalpha():
            cSummary += c.lower()
        elif c in string.whitespace and cSummary != '' and cSummary[-1] != ' ':
            cSummary += ' '
    cSummary = cSummary.split()
    return cSummary


def cleanSummaries(genres, summaries, verbose=False):
    if CLEAN_SUMMARY_MANUAL:
        summaries = list(map(lambda s: cleanSummaryManual(s)
                         [0:SUMMARY_LENGTH_MAX], summaries))
    else:
        summaries = list(map(lambda s: nltk.word_tokenize(s)
                         [0:SUMMARY_LENGTH_MAX], summaries))

    tmpGenres = []
    tmpSummaries = []
    for g, s in zip(genres, summaries):
        if len(s) >= SUMMARY_LENGTH_MIN:
            tmpGenres.append(g)
            tmpSummaries.append(s)
    genres = tmpGenres
    summaries = tmpSummaries

    if verbose > 1:
        print('\nwords:')
        printLen(summaries)
        print(f'\nlen(genres)={len(genres)}')
    return (genres, summaries)


def getWordIndex(summaries, verbose=False):
    wordIndex = countElements(chain.from_iterable(summaries))
    wordIndex = wordIndex[WORDS_DROP_TOP:WORDS_KEEP_TOP]
    wordIndex = list(map(lambda w: w[0], wordIndex))
    wordIndex = dict(zip(wordIndex, range(1, len(wordIndex)+1)))
    if verbose > 1:
        print(f'\nwordIndex(len={len(wordIndex)}):')
        #print(wordIndex)
    return wordIndex


def loadEmbedingIndex():
    embeddingsIndex = {}
    with open(EMBEDDING_FILE_PATH, encoding='UTF-8') as file:
        for line in file:
            word, coefs = line.split(maxsplit=1)
            coefs = np.fromstring(coefs, 'f', sep=' ')
            embeddingsIndex[word] = coefs
    return embeddingsIndex


def getEmbeddingMatrix(wordIndex, embedingsIndex):
    embeddingMatrix = np.zeros((max(wordIndex.values())+1, EMBEDDING_DIM))
    for word, i in wordIndex.items():
        if word in embedingsIndex:
            embeddingMatrix[i] = embedingsIndex[word]
    return embeddingMatrix


def calcPrevalance(summary, wordIndex):
    mappedSummary = np.zeros((len(wordIndex)))
    for word in summary:
        if word in wordIndex:
            mappedSummary[wordIndex[word]-1] += 1
    mappedSummary /= len(summary)
    return mappedSummary


def cleanData(dType='books',verbose=0):
    if verbose > 0:
        print('--------------------------------------------------------------------------')
        print("CleanData")
        print('--------------------------------------------------------------------------')

    if dType=='books':
        books = loadRawBooksData(verbose)
        genres, summaries = selectData(books, verbose=verbose)
    elif dType=='movies':
        movies = loadRawMoviesData(verbose)
        movies['genre']=movies['genre'].map(lambda g: g if g in GENRE_INDEX.keys() else None)
        movies=movies.dropna()
        genres=movies['genre']
        summaries=movies['summary']
    genres, summaries = cleanSummaries(genres, summaries, verbose=verbose)
    genres = genres[:TRAIN_SIZE+TEST_SIZE]
    summaries = summaries[:TRAIN_SIZE+TEST_SIZE]

    wordIndex = getWordIndex(summaries, verbose)
    embedingIndex = loadEmbedingIndex()
    embeddingMatrix = getEmbeddingMatrix(wordIndex, embedingIndex)

    shuffeledIndexes = tf.random.shuffle(
        tf.range(start=0, limit=len(genres), dtype=tf.int32))

    genres = np.array(list(map(GENRE_INDEX.get, genres)))
    genres = tf.gather(genres, shuffeledIndexes).numpy()
    if verbose > 1:
        print(f'\nfinal genres(len={len(genres)}):\n', genres)

    summariesWP = np.array(list(map(
        lambda summary: calcPrevalance(summary, wordIndex), summaries)))
    scaler = StandardScaler().fit(summariesWP)
    summariesWP = scaler.transform(summariesWP)
    summariesWP = tf.gather(summariesWP, shuffeledIndexes).numpy()
    if verbose > 1:
        print(f'\nfinal summariesWP(len={len(summariesWP)}):\n', summariesWP)

    summariesIndexed = list(map(lambda summary: list(map(
        lambda word: wordIndex[word] if word in wordIndex else 0, summary)), summaries))
    summariesIndexed = pad_sequences(
        summariesIndexed, padding='post', dtype=int, value=0)
    summariesIndexed = tf.gather(summariesIndexed, shuffeledIndexes).numpy()
    if verbose > 1:
        print(f'\nfinal summariesIndexed(len={len(summariesIndexed)}):\n',
              summariesIndexed)

    booksData = {
        'genres': (genres[:TRAIN_SIZE],
                   genres[TRAIN_SIZE:TRAIN_SIZE+TEST_SIZE]),
        'summaries': (summariesIndexed[:TRAIN_SIZE],
                      summariesIndexed[TRAIN_SIZE:TRAIN_SIZE+TEST_SIZE]),
        'summariesWP': (summariesWP[:TRAIN_SIZE],
                        summariesWP[TRAIN_SIZE:TRAIN_SIZE+TEST_SIZE]),  # WordPrevalances
        'wordIndex': wordIndex,
        'embeddingMatrix': embeddingMatrix
    }

    return booksData
