from .base4_spider import BaseHotSpider


class UCHotSpider1(BaseHotSpider):
    name = "uc_interact_hot"
    platform_id = 15
    hot_list_url = "https://m.uczzd.cn/iflow/api/v2/cmt/hotlist/get?page=1&size=10&uc_param_str=dnnivebichfrmintnwcpgieiwidsudpfmtsvsnut&kps_wg&auto=0&gi=bTkwBL2bl83vZHcInR1kmc%2Fj%2FY72&sv=ucrelease&ch=yzappstore%40&nt=2&bi=34464&mt=1bEANKVLPOHinAKDwLzIyjcsnO8K%2BVwM&nw=WIFI&dn=61177343034-ea334173&fr=android&ve=15.1.2.1202&ds=bTkwBEkwqZ1Xr3dJctxJ6etWgpZ%2Bc4ABBSP0732Z9rxUWw%3D%3D&wi=bTkwBPsIn23xXjvtXg%3D%3D&pc=AAQRAtQtd9XY54gmHPf775eHbuf%2BYbC9eehroE%2BrJhJ2hVnH8IpdbEg5gELNRVLXEQLbXw0JGarhS15SUL8Z6ZUD&pf=145&ni=bTkwBAt%2BwXzj2hzR1j8DlAqoEqTw6zAjhGIkBu%2BbtrolLjY%3D&sn=2210-61177343034-419d6b30&mi=OXF-AN10&ut=AARbJ4cpeOCLmBv%2B00WYXkvunjVZJ%2BeReru7ipC96EFxAQ%3D%3D"
    author_xpath = '//*[@id="infoBoxName"]'

    title_field = 'article_title'
    url_field = 'article_link'
    rank_field = 'hot_rank'

    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.uc1middlewares.RotateUserAgentMiddleware': 500,
            'hotsearchcrawler.uc1middlewares.UCRefererMiddleware': 500,
        },
        'CONCURRENT_REQUESTS': 4,
        'DOWNLOAD_DELAY': 0.5,
        'RETRY_TIMES': 3,
    }