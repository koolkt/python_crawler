<?php
class RedisQueue {
    private $redis;
    function connect($addr='127.0.0.1', $port=6379) {
        $this->redis = new Redis();
        $this->redis->connect($addr, $port);
    }

    function rq_gen_pop($name=null) {
        while (name and $this->redis->llen(name.':product_info')) {
            yield $this->redis->lpop(name);
        }
        return null;
    }

    function rq_get_data($name) {
        $item_generator = rq_gen_pop(name.':product_info');
        foreach($item_generator as $item) {
            print($item);
        }
    }

    function send_info($info, $name) {
        $info = json_encode($info);
        $this->redis->rpush(name.':product_info', info);
    }

    function close() {
        $redis->close();
    }
}

r = new RedisQueue();
r->rq_get_data("http://le-narguile.com");
?>
