import re
import scrapy 
import pickle as pkl
from bs4 import BeautifulSoup as bs
from scrapy.spiders import CrawlSpider

def read_file(): 
    return pkl.load(open("targets.p", "rb"))


class Uspto(CrawlSpider):
    name = 'uspto'
    start_urls = ['http://patft.uspto.gov/netahtml/PTO/search-bool.html']

    def parse(self, response):
#        firms = ['Market6 Inc', 'Steeleye Technology Inc', 'Skeed Co Ltd']
        firms = read_file()
        for firm in firms[:10]:
            yield scrapy.http.FormRequest.from_response(response, 
                                                        formname="TERM1", 
                                                        formdata={"TERM1":firm},
                                                        callback=self.parse_patent,
                                                        meta={'firm':firm})


    def parse_patent(self, response):
        temp = {}
        rows = response.xpath('//tr')
        if len(response.xpath('//table')) == 1: 
            return 

        elif len(response.xpath('//table')) > 3: 
            yield scrapy.http.Request(response.url,
                                      dont_filter=True,
                                      callback=self.parse_patent_detail,
                                      meta={'firm': response.meta['firm']})

        elif len(response.xpath('//table')) == 3:
            for idx, row in enumerate(rows):
                if idx < 2: 
                    continue
                elif (idx >= 2) and (idx < len(rows)):
                    hrefs = [x for x in row.xpath('td/a/@href').extract()]
                    patent_detail_page = 'http://patft.uspto.gov' + hrefs[0]

                    row_data = [x for x in row.xpath('td//text()').extract() if x != '\n' and x != '\n   ']
                    if len(row_data) != 0:
                        no = row_data[0]
                        patent_no = row_data[1]
                        patent_title = row_data[2].strip().replace('\n     ',' ')

                        yield scrapy.http.Request(patent_detail_page,
                                                  callback=self.parse_patent_detail,
                                                  meta={'firm': response.meta['firm'],
                                                        'no' : no,
                                                        'patent_no' : patent_no,
                                                        'patent_title' : patent_title})

            navigation = response.xpath('//table')[2].xpath('tr/td/a')
            for navi in navigation:
                if navi.xpath('img//@alt').extract() == ['[NEXT_LIST]']:
                    next_page = 'http://patft.uspto.gov' + navi.xpath('@href').extract_first()

                    yield scrapy.http.Request(next_page, 
                                              callback=self.parse_patent, 
                                              meta={'firm':response.meta['firm']})

    def parse_patent_detail(self, response):
        item = response.meta
        item['url'] = response.url

        # metadata - authors and date
        temp = response.xpath('//table')[2].xpath('tr')[1].xpath('td//text()').extract()
        temp = [x.strip() for x in temp if len(x.strip()) != 0]
        authors = temp[0].replace('\n, ', '').replace('\xa0', '')
        date = temp[1]
        item['authors'] = authors
        item['application_date'] = date

        # abstract
        abstract = response.xpath('//p//text()')[0].extract().replace('\n   ', '').strip()
        item['abstract'] = abstract

        soup = bs(response.body, 'lxml')
        soup_content = soup.prettify()
        tabletags_list = soup.find_all('table')
        fonttags_list = soup.find_all('font')
        titletags_list = soup.find_all('title')
        trtags_list = soup.find_all('tr')

        if response.xpath('/html/body/font/text()').extract():

            # GRANTED DATE:
            btagsintable2_list  = tabletags_list[2].findAll('b')
            length =  btagsintable2_list.__len__()
            date_string = "".join(btagsintable2_list[length-1])
            granted_date = (date_string.replace('\n','')).lstrip()

            ## FILING DATE:
            filed_date_expression = re.compile('Filed:\n\s+</th>\n\s+<td align="left" width="90%">\n\s+<b>\s+(.*?)</b>',re.DOTALL)
            filed_date = re.findall(filed_date_expression,soup_content)
            filed_date_string = str(filed_date[0])
            if filed_date_string == '</b>':
                filed_date_string = nullstring
            tmp_filed_date_str = filed_date_string.replace('     ','')
            filed_date_str = tmp_filed_date_str.replace('\n','')


            item['granted_date'] = granted_date
            item['filed_date'] = filed_date_str

        yield item

