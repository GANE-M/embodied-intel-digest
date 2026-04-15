$env:EMAIL_TO="wangwangathnu@gmail.com,375477695@qq.com"
$env:EMAIL_FROM="375477695@qq.com"
$env:SMTP_HOST="smtp.qq.com"
$env:SMTP_PORT="587"
$env:SMTP_USE_SSL="false"
$env:SMTP_USERNAME="375477695@qq.com"
$env:SMTP_PASSWORD="uygqnudzhpvvbhjg"
$env:SUMMARY_MODE="template"
$env:LOOKBACK_HOURS="168"  # 例如：设置为抓取过去 72 小时（3天）的数据
$env:STORE_TYPE="json"
$env:STATE_DIR="./state_test_fresh"

# ======== 新增：DeepSeek 大模型配置 ========
$env:LLM_API_KEY="sk-3f492a9a537745449387de01199f8009"
$env:LLM_BASE_URL="https://api.deepseek.com"
$env:LLM_MODEL="deepseek-chat"
$env:LLM_TIMEOUT_SEC="75"
$env:LLM_MAX_TOKENS="768"



python -m app.main