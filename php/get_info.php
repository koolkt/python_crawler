<?php

class RedisQueue {
    private $redis;
    function connect($addr='127.0.0.1', $port=6379) {
        $this->redis = new Redis();
        $this->redis->connect($addr, $port);
        echo "connecting...\n";
    }

    function rq_gen_pop($n) {
        if (!$n) {
            echo "No name specified to rq_get_data!";
            return;
        }
        while ($n) {
            #echo $this->redis->llen($n.':product_info');
            #echo $n.':product_info'.'\n';
            yield $this->redis->lpop($n);
        }
        return null;
    }

    function rq_get_data($name) {
        $item_generator = $this->rq_gen_pop($name.':product_info');
        print_r($item_generator);
        foreach($item_generator as $item) {
            echo $item;
        }
    }

    function send_info($info, $name) {
        $info = json_encode($info);
        $this->redis->rpush($name.':product_info', info);
    }

    function close() {
        $redis->close();
    }
}

$r = new RedisQueue();
$r->connect();
$r->rq_get_data("http://le-narguile.com");
?>
