from scrapy.pipelines.images import ImagesPipeline
from scrapy.http import Request
import os

class BookCoverPipeline(ImagesPipeline):

    def get_media_requests(self, item, info):
        for image_url in item['image_urls']:
            yield Request(image_url, meta={'book_dir': item["book_dir"]})

    def file_path(self, request, response=None, info=None, *, item=None):
        book_dir = request.meta['book_dir']
        image_name = os.path.basename(request.url)
        return os.path.join(book_dir, image_name)