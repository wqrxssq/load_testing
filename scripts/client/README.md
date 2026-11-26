# Клиенты рыночных потоков

Два скрипта подписываются на один логический поток одной биржи и печатают сырые сообщения. Локальную книгу они не собирают: это наблюдатели протокола, а не обработчик.

Оба говорят на одних и тех же трёх типах данных. Инструмент (`--security`) передаётся так, как его пишет сама биржа.

| Тип данных | Что это | Binance USD-M | OKX |
|---|---|---|---|
| `trades` | лента сделок | `<symbol>@aggTrade` | канал `trades` |
| `book_tickers` | лучший bid и лучший ask | `<symbol>@bookTicker` | канал `bbo-tbt` |
| `incrementals` | патчи стакана | `<symbol>@depth@100ms` | канал `books` |

## Установка

```bash
/usr/bin/python3 -m venv scripts/client/.venv
source scripts/client/.venv/bin/activate
pip install -r scripts/client/requirements.txt
```

## Запуск

```bash
python scripts/client/binance.py --type trades --security BTCUSDT
python scripts/client/binance.py --type book_tickers --security BTCUSDT
python scripts/client/binance.py --type incrementals --security BTCUSDT

python scripts/client/okx.py --type trades --security BTC-USDT-SWAP
python scripts/client/okx.py --type book_tickers --security BTC-USDT-SWAP
python scripts/client/okx.py --type incrementals --security BTC-USDT-SWAP
```

`--count N` останавливает скрипт после N рыночных сообщений. `--compact` печатает каждое сообщение одной строкой.

На OKX бессрочный контракт, парный к фьючерсу `BTCUSDT`, называется `BTC-USDT-SWAP`. Спот на том же сокете — `BTC-USDT`.

## Binance USD-M

combined stream через URL. Три типа открывают два разных сокета:

```text
wss://fstream.binance.com/market/stream?streams=btcusdt@aggTrade
wss://fstream.binance.com/public/stream?streams=btcusdt@bookTicker
wss://fstream.binance.com/public/stream?streams=btcusdt@depth@100ms
```

```json
{
  "stream": "btcusdt@aggTrade",
  "data": {}
}
```

Сервер шлёт protocol-level ping примерно раз в три минуты. Библиотека `websockets` отвечает pong сама.

### trades → `aggTrade`

Пачка раз в 100 мс: исполнения с одной ценой и одной стороной taker склеиваются в одно сообщение. Сделки страхового фонда и ADL в этот поток не входят.

```json
{
  "e": "aggTrade",
  "E": 1795734368597,
  "s": "BTCUSDT",
  "a": 3552938637,
  "p": "60505.80",
  "q": "0.015",
  "nq": "0.015",
  "f": 8346082369,
  "l": 8346082369,
  "T": 1795734368447,
  "m": true,
  "st": 1
}
```

| Поле | Смысл |
|---|---|
| `e` | тип события |
| `E` | время события, мс |
| `s` | инструмент |
| `a` | id агрегата |
| `p` | цена |
| `q` | полный объём агрегата, включая RPI-ордера |
| `nq` | объём без сделок, где участвовал RPI-ордер |
| `f`, `l` | первый и последний trade id внутри агрегата |
| `T` | время сделки, мс |
| `m` | покупатель был мейкером |
| `st` | тип контракта после слияния UM/CM: `1` — USD-M, `2` — COIN-M |

### book_tickers → `bookTicker`

Реальное время, при каждом изменении лучшей цены или её объёма.

RPI-заявки в этот поток не попадают.

```json
{
  "e": "bookTicker",
  "u": 12251731250570,
  "s": "BTCUSDT",
  "ps": "BTCUSDT",
  "b": "60505.80",
  "B": "10.437",
  "a": "60505.90",
  "A": "1.016",
  "T": 1795734375925,
  "E": 1795734375926,
  "st": 1
}
```

| Поле | Смысл |
|---|---|
| `u` | id обновления стакана |
| `s` | инструмент |
| `ps` | пара. У бессрочного `BTCUSDT` совпадает с `s`, у квартального контракта это базовая пара |
| `b`, `B` | лучшая цена покупки и объём |
| `a`, `A` | лучшая цена продажи и объём |
| `T`, `E` | время сделки и время события, мс |
| `st` | `1` — USD-M, `2` — COIN-M |

### incrementals → `depth@100ms`

Патч стакана раз в 100 мс. В `b` и `a` только изменившиеся уровни. Количество абсолютное: «на этой цене теперь столько». `"0"` удаляет уровень. Номера `U`/`u` — диапазон внутренних обновлений в пакете, `pu` должен совпасть с `u` предыдущего пакета.

RPI-заявки в уровни не входят. Сообщение за 100 мс на ликвидном контракте длинное: в одной пачке сотни уровней.

```json
{
  "e": "depthUpdate",
  "E": 1795734387725,
  "T": 1795734387724,
  "s": "BTCUSDT",
  "ps": "BTCUSDT",
  "U": 157,
  "u": 160,
  "pu": 149,
  "b": [["60483.40", "0.096"]],
  "a": [["60505.90", "0"]],
  "st": 1
}
```

`ps` и `st` значат то же, что в book ticker.

Документация:

- [WebSocket Market Streams](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams)
- [Разделение URL public / market / private](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Important-WebSocket-Change-Notice)
- [Aggregate Trade Streams](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams)
- [Individual Symbol Book Ticker](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Individual-Symbol-Book-Ticker-Streams)
- [Diff Book Depth](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Diff-Book-Depth-Streams)
- [REST-снимок стакана](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Order-Book)

## OKX

Один публичный сокет:

```text
wss://ws.okx.com/ws/v5/public
```

Дальше JSON:

```json
{
  "id": "1",
  "op": "subscribe",
  "args": [
    {"channel": "books", "instId": "BTC-USDT-SWAP"}
  ]
}
```

Ответ на подписку (`event: subscribe` или `event: error`) печатается в stderr и в счётчик `--count` не входит. Рыночные пуши приходят с тем же `arg`, по которому подписывались.

Если 30 секунд нет трафика, OKX закрывает соединение. Скрипт раз в 20 секунд шлёт текст `ping` и ждёт текст `pong`. На входящий текст `ping` отвечает `pong`.

### trades

Пуш при каждой сделке. Одно сообщение может склеивать несколько исполнений одного taker-ордера по одной цене: сколько их было, лежит в `count`.

```json
{
  "arg": {"channel": "trades", "instId": "BTC-USDT-SWAP"},
  "data": [
    {
      "instId": "BTC-USDT-SWAP",
      "tradeId": "130639474",
      "px": "42219.9",
      "sz": "0.12",
      "side": "buy",
      "ts": "1630048897897",
      "count": "3",
      "source": "0",
      "seqId": 1234
    }
  ]
}
```

| Поле | Смысл |
|---|---|
| `px`, `sz` | цена и объём (для SWAP/FUTURES объём в контрактах) |
| `side` | сторона taker: `buy` или `sell` |
| `tradeId` | последний trade id в агрегате |
| `count` | сколько исполнений схлопнуто |
| `source` | `0` обычный ордер, `1` ордер программы ликвидности |
| `ts` | время исполнения, мс |
| `seqId` | номер сообщения; у одновременных сделок может совпасть |

### book_tickers → `bbo-tbt`

Один уровень с каждой стороны. Первый пуш — снимок, дальше новый снимок каждые 10 мс, если верх изменился. Это не дельта: пришедшие массивы и есть текущий лучший bid/ask.

```json
{
  "arg": {"channel": "bbo-tbt", "instId": "BTC-USDT-SWAP"},
  "data": [
    {
      "asks": [["64250.2", "15", "0", "2"]],
      "bids": [["64250.1", "8", "0", "3"]],
      "ts": "1597026383085",
      "seqId": 123456
    }
  ]
}
```

Уровень: `["цена", "объём", "0", "число ордеров"]`. Третье поле — остаток старого формата.

### incrementals → `books`

Первое сообщение — `action: "snapshot"`, до 400 уровней, `prevSeqId: -1`. Дальше каждые 100 мс `action: "update"` с изменившимися уровнями. Объём абсолютный, `"0"` удаляет цену. Следующее сообщение обязано прийти с `prevSeqId`, равным `seqId` предыдущего. `checksum` в ответе остаётся, но с июня 2026 всегда `0`; непрерывность смотрят по `seqId` / `prevSeqId`.

```json
{
  "arg": {"channel": "books", "instId": "BTC-USDT-SWAP"},
  "action": "update",
  "data": [
    {
      "asks": [["64251.0", "0", "0", "0"]],
      "bids": [["64250.1", "3", "0", "1"]],
      "ts": "1597026383085",
      "checksum": 0,
      "prevSeqId": 123456,
      "seqId": 123457
    }
  ]
}
```

Документация:

- [WebSocket: подключение, ping, subscribe](https://www.okx.com/docs-v5/en/#overview-websocket-connect)
- [Trades channel](https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-trades-channel)
- [Order book channel](https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-order-book-channel) (`books`, `bbo-tbt` и соседние каналы на одной странице)
- [Как устроены снимки и инкременты](https://www.okx.com/docs-v5/trick_en/#market-data)
