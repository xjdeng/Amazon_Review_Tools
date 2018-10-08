#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Written as part of https://www.scrapehero.com/how-to-scrape-amazon-product-reviews-using-python/		
from lxml import html  
import json
import requests
import re
from dateutil import parser as dateparser
from time import sleep
from fake_useragent import UserAgent
import random
from gensim.summarization.summarizer import summarize
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request is being made")

ua = UserAgent()

def ParseReviews_url(amazon_url):
	# for i in range(5):
	# 	try:
	#This script has only been tested with Amazon.com
	#amazon_url  = 'http://www.amazon.com/dp/'+asin
	# Add some recent user agent to prevent amazon from blocking the request 
	# Find some chrome user agent strings  here https://udger.com/resources/ua-list/browser-detail?browser=Chrome
	headers = {'User-Agent': ua.random}
	page = requests.get(amazon_url,headers = headers,verify=False)
	page_response = page.text

	parser = html.fromstring(page_response)
	XPATH_AGGREGATE = '//span[@id="acrCustomerReviewText"]'
	XPATH_REVIEW_SECTION_1 = '//div[contains(@id,"reviews-summary")]'
	XPATH_REVIEW_SECTION_2 = '//div[@data-hook="review"]'

	XPATH_AGGREGATE_RATING = '//table[@id="histogramTable"]//tr'
	XPATH_PRODUCT_NAME = '//h1//span[@id="productTitle"]//text()'
	XPATH_PRODUCT_PRICE  = '//span[@id="priceblock_ourprice"]/text()'
	
	raw_product_price = parser.xpath(XPATH_PRODUCT_PRICE)
	product_price = ''.join(raw_product_price).replace(',','')

	raw_product_name = parser.xpath(XPATH_PRODUCT_NAME)
	product_name = ''.join(raw_product_name).strip()
	total_ratings  = parser.xpath(XPATH_AGGREGATE_RATING)
	reviews = parser.xpath(XPATH_REVIEW_SECTION_1)
	if not reviews:
		reviews = parser.xpath(XPATH_REVIEW_SECTION_2)
	ratings_dict = {}
	reviews_list = []
	
	if not reviews:
		raise ValueError('unable to find reviews in page')

	#grabing the rating  section in product page
	for ratings in total_ratings:
		extracted_rating = ratings.xpath('./td//a//text()')
		if extracted_rating:
			rating_key = extracted_rating[0] 
			raw_raing_value = extracted_rating[1]
			rating_value = raw_raing_value
			if rating_key:
				ratings_dict.update({rating_key:rating_value})
	
	#Parsing individual reviews
	for review in reviews:
		XPATH_RATING  = './/i[@data-hook="review-star-rating"]//text()'
		XPATH_REVIEW_HEADER = './/a[@data-hook="review-title"]//text()'
		XPATH_REVIEW_POSTED_DATE = './/span[@data-hook="review-date"]//text()'
		XPATH_REVIEW_TEXT_1 = './/span[@data-hook="review-body"]//text()'
		XPATH_REVIEW_TEXT_2 = './/div//span[@data-action="columnbalancing-showfullreview"]/@data-columnbalancing-showfullreview'
		XPATH_REVIEW_COMMENTS = './/span[@class="review-comment-total aok-hidden"]//text()'
		XPATH_AUTHOR  = './/a[@data-hook="review-author"]//text()'
		XPATH_REVIEW_TEXT_3  = './/div[contains(@id,"dpReviews")]/div/text()'
		
		raw_review_author = review.xpath(XPATH_AUTHOR)
		raw_review_rating = review.xpath(XPATH_RATING)
		raw_review_header = review.xpath(XPATH_REVIEW_HEADER)
		raw_review_posted_date = review.xpath(XPATH_REVIEW_POSTED_DATE)
		raw_review_text1 = review.xpath(XPATH_REVIEW_TEXT_1)
		raw_review_text2 = review.xpath(XPATH_REVIEW_TEXT_2)
		raw_review_text3 = review.xpath(XPATH_REVIEW_TEXT_3)

		#cleaning data
		author = ' '.join(' '.join(raw_review_author).split())
		review_rating = ''.join(raw_review_rating).replace('out of 5 stars','')
		review_header = ' '.join(' '.join(raw_review_header).split())

		try:
			review_posted_date = dateparser.parse(''.join(raw_review_posted_date)).strftime('%d %b %Y')
		except:
			review_posted_date = None
		review_text = ' '.join(' '.join(raw_review_text1).split())

		#grabbing hidden comments if present
		if raw_review_text2:
			json_loaded_review_data = json.loads(raw_review_text2[0])
			json_loaded_review_data_text = json_loaded_review_data['rest']
			cleaned_json_loaded_review_data_text = re.sub('<.*?>','',json_loaded_review_data_text)
			full_review_text = review_text+cleaned_json_loaded_review_data_text
		else:
			full_review_text = review_text
		if not raw_review_text1:
			full_review_text = ' '.join(' '.join(raw_review_text3).split())

		raw_review_comments = review.xpath(XPATH_REVIEW_COMMENTS)
		review_comments = ''.join(raw_review_comments)
		review_comments = re.sub('[A-Za-z]','',review_comments).strip()
		review_dict = {
							'review_comment_count':review_comments,
							'review_text':full_review_text,
							'review_posted_date':review_posted_date,
							'review_header':review_header,
							'review_rating':int(float(review_rating)),
							'review_author':author

						}
		reviews_list.append(review_dict)

	data = {
				'ratings':ratings_dict,
				'reviews':reviews_list,
				'url':amazon_url,
				'price':product_price,
				'name':product_name
			}
	return data
	# 	except ValueError:
	# 		print("Retrying to get the correct response")

	# return {"error":"failed to process the page","asin":asin}
    
def download_reviews(url, startpage, endpage, wait = (1, 5), verbose = True):
    if url[-1] == "1":
        baseurl = url[0:-1]
    else:
        baseurl = url
    results = None
    for i in range(startpage, endpage + 1):
        if verbose == True:
            print("Downloading page {} of {}".format(i, endpage))
        if isinstance(wait, tuple):
            sleep(random.randrange(*wait))
        else:
            sleep(wait)
        myurl = baseurl + str(i)
        try:
            rawout = ParseReviews_url(myurl)
            if results is None:
                results = rawout
            else:
                results['reviews'] += rawout['reviews']
        except ValueError:
            if verbose == True:
                print("No reviews found, skipping.")
    return results

def combine_reviews(data, minrating = 4, shuffle = True):
    goodreviews = [r['review_text'] for r in data['reviews'] if \
                   r['review_rating'] >= minrating]
    if shuffle == True:
        random.shuffle(goodreviews)
    return "\n".join(goodreviews)

def summary(text, words = None):
    if isinstance(words, tuple):
        words = random.randrange(*words)
    return summarize(text, word_count = words).replace('\n','  ')

def to_file(text, output = "output", tries = None):
    if tries is None:
        outfile = output + ".txt"
    else:
        outfile = output + str(tries) + ".txt"
    try:
        f = open(outfile, "w", encoding = "utf-8")
        f.write(text)
        f.close
    except IOError:
        if tries is None:
            trynext = 1
        else:
            trynext = tries + 1
        to_file(text, output, trynext)

def run(url, startpage, endpage, wait = (1, 5), minrating = 4, shuffle = True,\
        words = None, output = "output", verbose = True):
    data = download_reviews(url, startpage, endpage, wait, verbose)
    reviews = combine_reviews(data, minrating, shuffle)
    mysummary = summary(reviews, words)
    to_file(mysummary, output)
    return data

def run_data(data, minrating = 4, shuffle = True, words = None, output = \
             "output"):
    reviews = combine_reviews(data, minrating, shuffle)
    mysummary = summary(reviews, words)
    to_file(mysummary, output)    