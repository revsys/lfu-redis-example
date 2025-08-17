# LRU vs LFU Redis Demo 

Everyone defaults to LRU caching, but when bots create 500,000 sessions per hour, LFU is your best friend.

Frank wrote up a detailed description of why you should consider using an [LFU cache for user sessions](https://www.revsys.com/tidbits/sometimes-lfu-lru/). 

# Quick Video Explanation 

[![LFU is better than LRU for storing browser sessions](https://img.youtube.com/vi/lSNdp7qpqVo/0.jpg)](https://www.youtube.com/watch?v=lSNdp7qpqVo)

## Which cache algorithm is right for you? 

![Image with LFU on one side and LRU on the other](./lfu-vs-lru.png)


