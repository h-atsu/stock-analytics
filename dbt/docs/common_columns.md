{% docs trade_date %}
東証の取引日。日本時間基準の暦日です。
{% enddocs %}

{% docs snapshot_date %}
銘柄マスターまたは上場銘柄一覧を取得した基準日です。
{% enddocs %}

{% docs security_code %}
東証銘柄コード。英数字を含み得る5文字の文字列として扱います。
{% enddocs %}

{% docs yahoo_ticker %}
Yahoo Financeで使用するticker。東証銘柄では通常、銘柄コードに`.T`を付けた値です。
{% enddocs %}

{% docs ingested_at %}
ingestionがParquetへ保存したUTC timestamp。同一business keyの再取得履歴から最新行を選ぶために使用します。
{% enddocs %}

{% docs source_endpoint %}
行を取得したAPI endpointまたは取得処理を表すlineage値です。
{% enddocs %}
