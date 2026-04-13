$env:EMAIL_TO="wangwangathnu@gmail.com,375477695@qq.com"
$env:EMAIL_FROM="375477695@qq.com"
$env:SMTP_HOST="smtp.qq.com"
$env:SMTP_PORT="587"
$env:SMTP_USE_SSL="false"
$env:SMTP_USERNAME="375477695@qq.com"
$env:SMTP_PASSWORD="hlpezsjqeipbbgbb"
$env:SUMMARY_MODE="template"
$env:LOOKBACK_HOURS="168"  # 例如：设置为抓取过去 72 小时（3天）的数据
$env:STORE_TYPE="json"
$env:STATE_DIR="./state_test_fresh"

python -m app.main