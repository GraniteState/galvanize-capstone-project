from src import prepare_court_data
import pyspark as ps
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from pyspark.ml.feature import Tokenizer, RegexTokenizer, StopWordsRemover, NGram, \
        CountVectorizer, IDF, Word2Vec
from pyspark.sql.types import StructType, StructField, IntegerType, StringType, \
        FloatType, ArrayType, BooleanType
from nltk.stem import SnowballStemmer
from pyspark.sql.functions import udf, col
from pyspark.sql.functions import explode, collect_list


# create an RDD from the data, choose number of rows to include
opinion_lst = prepare_court_data.create_df_from_tar('data/opinions_wash.tar.gz', 100)
opinion_rdd = sc.parallelize(opinion_lst, 15)

# define the subset of columns to use and write it into a schema
df_columns = ['cluster_id', 'resource_id', 'parsed_text', 'per_curiam', 'opinions_cited', 'type']
# fields = [StructField(field_name, StringType(), True) for field_name in df_columns]
fields = [StructField('cluster_id', IntegerType(), True), 
        StructField('resource_id', IntegerType(), True),
        StructField('parsed_text', StringType(), True),
        StructField('per_curiam', BooleanType(), True),
        StructField('opinions_cited', ArrayType(IntegerType()), True),
        StructField('type', StringType(), True)]
schema = StructType(fields)

# create the dataframe from just the columns we want
reduced_rdd = opinion_rdd.map(lambda row: [row.get(key, '') for key in df_columns])
opinion_df = spark.createDataFrame(reduced_rdd, schema)

# Parse tokens from text, remove stopwords
# tokenizer = Tokenizer(inputCol='parsed_text', outputCol='tokens')
regexTokenizer = RegexTokenizer(inputCol="parsed_text", outputCol="raw_tokens", pattern="\\W", minTokenLength=3)
remover = StopWordsRemover(inputCol='raw_tokens', outputCol='tokens_stop')
opinion_df = regexTokenizer.transform(opinion_df)
opinion_df = remover.transform(opinion_df)

# use a udf to stem the tokens using the nltk SnowballStemmer with the English dictionary
opinion_stemm = SnowballStemmer('english')
udfStemmer = udf(lambda tokens: [opinion_stemm.stem(word) for word in tokens], ArrayType(StringType()))
opinion_df = opinion_df.withColumn('tokens', udfStemmer(opinion_df.tokens_stop))

# create n-grams
bigram = NGram(inputCol='tokens', outputCol='bigrams', n=2)
trigram = NGram(inputCol='tokens', outputCol='trigrams', n=3)
opinion_df = bigram.transform(opinion_df)
opinion_df = trigram.transform(opinion_df)

# CountVectorizer
cv = CountVectorizer(inputCol='tokens', outputCol='token_countvector', minDF=10.0)
opinion_cv_model = cv.fit(opinion_df)
opinion_df = opinion_cv_model.transform(opinion_df)

# IDF
idf = IDF(inputCol='token_countvector', outputCol='token_idf', minDocFreq=10)
opinion_idf_model = idf.fit(opinion_df)
opinion_df = opinion_idf_model.transform(opinion_df)

# Word2Vec
w2v_2d = Word2Vec(vectorSize=2, minCount=2, inputCol='tokens', outputCol='word2vec_2d')
w2v_large = Word2Vec(vectorSize=250, minCount=2, inputCol='tokens', outputCol='word2vec_large')
opinion_w2v2d_model = w2v_2d.fit(opinion_df)
opinion_w2vlarge_model = w2v_large.fit(opinion_df)
opinion_df = opinion_w2v2d_model.transform(opinion_df)
opinion_df = opinion_w2vlarge_model.transform(opinion_df)

# retrieve top 10 number of words for the document, assumes existence of 'row' containg one row from the dataframe
np.array(opinion_cv_model.vocabulary)[row['token_idf'].indices[np.argsort(row['token_idf'].values)]][:-11:-1]

# save and retrieve dataframe
opinion_df.write.save('data/opinions-spark-data.json', format='json', mode='overwrite')
opinion_df = = spark.read.json('data/opinions-spark-data.json')

# extract the vector from a specific document and take the cosine similarity for all other documents, show the ten nearest
ref_vec = opinion_df.filter(opinion_df.resource_id == '3990749').first()['word2vec_large']
udfSqDist = udf(lambda cell: float(ref_vec.squared_distance(cell)), FloatType())
opinion_df.withColumn('squared_distance', udfSqDist(opinion_df.word2vec_large)).sort(col('squared_distance'), ascending=True).select('cluster_id', 'resource_id', 'squared_distance').show(10)

# create a list of terms connected to their stems
df_wordcount = spark.createDataFrame(lst_wordcount.agg({"*": "count"}).collect())
df_stems = df_wordcount.withColumn('stem', udf(lambda term: opinion_stemm.stem(term), StringType())(col('terms'))).groupBy('stem').agg(collect_list('terms').alias('terms'))
df_stems.select('terms').filter(df_stems.stem == 'art').first()[0]
