# Step2API

灏?[闃惰穬鏄熻景 (stepfun.com)](https://www.stepfun.com/) Web 瀵硅瘽鑳藉姏杞崲涓?OpenAI 鍏煎 API銆?
**閲嶈鍏嶈矗澹版槑**

鏈粨搴撲粎渚涘涔犮€佺爺绌躲€佷釜浜哄疄楠屽拰鍐呴儴楠岃瘉浣跨敤锛屼笉鎻愪緵浠讳綍褰㈠紡鐨勫晢涓氭巿鏉冦€侀€傜敤鎬т繚璇佹垨缁撴灉淇濊瘉銆備綔鑰呬笉瀵瑰洜浣跨敤銆佷慨鏀广€佸垎鍙戙€侀儴缃叉垨渚濊禆鏈」鐩€屼骇鐢熺殑浠讳綍鐩存帴鎴栭棿鎺ユ崯澶便€佽处鍙峰皝绂併€佹暟鎹涪澶便€佹硶寰嬮闄╂垨绗笁鏂圭储璧旇礋璐ｃ€傝鍕垮皢鏈」鐩敤浜庤繚鍙嶆湇鍔℃潯娆俱€佸崗璁€佹硶寰嬫硶瑙勬垨骞冲彴瑙勫垯鐨勫満鏅€?
---

## 鏋舵瀯姒傝

```
Client (OpenAI SDK / 鍏煎瀹㈡埛绔?
        鈹?        鈻?   Step2API (FastAPI)
        鈹?   鈹屸攢鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹?   鈹?Account 鈹? 鈫?澶氳处鍙疯疆璇?+ 骞跺彂鎺у埗
   鈹? Pool   鈹?   鈹斺攢鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹?        鈹?   鈹屸攢鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹?   鈹?StepFun 鈹? 鈫?SMS 鐧诲綍 / Token 鍒锋柊
   鈹? Auth   鈹?   鈹斺攢鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹?        鈹?   鈹屸攢鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹?   鈹? Chat   鈹? 鈫?浼氳瘽绠＄悊 / 娴佸紡鍝嶅簲
   鈹?Session 鈹?   鈹斺攢鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹?        鈹?   鈹屸攢鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹?   鈹係tepFun  鈹? Connect/gRPC-Web API
   鈹俉eb Chat 鈹?   鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

## 鏍稿績鑳藉姏

| 鑳藉姏 | 璇存槑 |
|------|------|
| OpenAI 鍏煎 | `GET /v1/models`, `POST /v1/chat/completions` (娴佸紡 + 闈炴祦寮? |
| 澶氳处鍙疯疆璇?| 鑷姩 token 鍒锋柊銆佸苟鍙戞Ы浣?+ 绛夊緟闃熷垪 |
| 閴存潈妯″紡 | API Key 鎵樼妯″紡 / 鐩撮€?Token 妯″紡 |
| 妯″瀷鍒悕 | 鏀寔 gpt-4銆乧laude-sonnet-4-6 绛夊埆鍚嶆槧灏?|
| CORS 鏀寔 | 缁熶竴鍏佽璺ㄥ煙璇锋眰 |
| SMS 鐧诲綍 | 鏀寔 Admin API 瑙﹀彂鐭俊楠岃瘉鐮佺櫥褰?|

## 蹇€熷紑濮?
### 鏂瑰紡涓€锛氭湰鍦版簮鐮佽繍琛?
```bash
# 1. 鍏嬮殕浠撳簱
git clone <repo_url> step2api
cd step2api

# 2. 瀹夎渚濊禆
pip install -e .

# 3. 閰嶇疆
cp config.example.json config.json
# 缂栬緫 config.json锛屽～鍏ヤ綘鐨?StepFun 璐﹀彿淇℃伅

# 4. 鍚姩
python -m step2api.main
# 鎴?step2api
```

榛樿璁块棶鍦板潃锛歚http://127.0.0.1:5001`

### 鏂瑰紡浜岋細uvicorn 鐩存帴鍚姩

```bash
pip install -r requirements.txt
uvicorn step2api.main:app --host 127.0.0.1 --port 5001
```

## 閰嶇疆璇存槑

```jsonc
{
  "host": "127.0.0.1",
  "port": 5001,

  // API 瀵嗛挜锛堝鎴风璇锋眰鏃朵娇鐢級
  "keys": ["sk-step2api-your-secret-key"],
  "api_keys": [
    {"key": "sk-step2api-your-secret-key", "name": "default"}
  ],

  // 璐﹀彿鍒楄〃锛圫tepFun 鎵嬫満鍙凤級
  "accounts": [
    {"phone": "+86 13800138000", "name": "account1"}
  ],

  // 妯″瀷鍒悕鏄犲皠
  "model_aliases": {
    "gpt-4": "step-3.5-flash",
    "gpt-4o": "step-3.5-flash",
    "claude-sonnet-4-6": "step-3.5-flash",
    "claude-opus-4-6": "step-3.5-flash"
  },

  // 杩愯鏃堕厤缃?  "runtime": {
    "account_max_inflight": 2,  // 姣忚处鍙锋渶澶у苟鍙戞暟
    "account_max_queue": 4,     // 绛夊緟闃熷垪涓婇檺
    "token_refresh_interval": 600
  },

  // 瀵硅瘽鑷姩娓呯悊
  "auto_delete": {
    "mode": "none"  // none / single / all
  },

  // 鎬濊€冩彁绀烘敞鍏?  "thinking_injection": {
    "enabled": true,
    "prompt": ""
  }
}
```

## 閴存潈妯″紡

| 妯″紡 | 璇存槑 |
|------|------|
| 鎵樼璐﹀彿妯″紡 | Bearer / x-api-key 浼犲叆 config.keys 涓殑 key锛岀敱鏈嶅姟鑷姩杞閫夋嫨璐﹀彿 |
| 鐩撮€?Token 妯″紡 | 浼犲叆 token 涓嶅湪 config.keys 涓椂锛岀洿鎺ヤ綔涓?StepFun token 閫忎紶 |

鍙€夎姹傚ご `X-Step2-Target-Account`锛氭寚瀹氫娇鐢ㄦ煇涓处鍙凤紙鍊间负 phone 鎴?name锛夈€?
## 浣跨敤绀轰緥

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-step2api-your-secret-key",
    base_url="http://127.0.0.1:5001/v1"
)

# 闈炴祦寮?response = client.chat.completions.create(
    model="step-3.5-flash",
    messages=[
        {"role": "user", "content": "浣犲ソ锛岃浠嬬粛涓€涓嬮樁璺冩槦杈?}
    ]
)
print(response.choices[0].message.content)

# 娴佸紡
stream = client.chat.completions.create(
    model="step-3.5-flash",
    messages=[
        {"role": "user", "content": "鍐欎竴棣栧叧浜嶢I鐨勮瘲"}
    ],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

```bash
# curl 闈炴祦寮?curl http://127.0.0.1:5001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-step2api-your-secret-key" \
  -d '{
    "model": "step-3.5-flash",
    "messages": [{"role": "user", "content": "浣犲ソ"}]
  }'

# curl 娴佸紡
curl http://127.0.0.1:5001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-step2api-your-secret-key" \
  -d '{
    "model": "step-3.5-flash",
    "messages": [{"role": "user", "content": "浣犲ソ"}],
    "stream": true
  }'
```

## Admin API

| 绔偣 | 璇存槑 |
|------|------|
| `GET /admin/queue/status` | 鏌ョ湅璐﹀彿姹犲苟鍙戠姸鎬?|
| `GET /admin/accounts` | 鍒楀嚭鎵€鏈夐厤缃殑璐﹀彿 |
| `POST /admin/accounts/send-sms` | 涓烘寚瀹氳处鍙峰彂閫佺煭淇￠獙璇佺爜 |
| `POST /admin/accounts/login` | 浣跨敤楠岃瘉鐮佸畬鎴愮櫥褰?|

## 杩愯鐘跺喌鎺㈡祴

| 绔偣 | 璇存槑 |
|------|------|
| `GET /healthz` | 瀛樻椿鎺㈤拡 |
| `GET /readyz` | 灏辩华鎺㈤拡 |

## 鐜鍙橀噺

| 鍙橀噺 | 璇存槑 | 榛樿鍊?|
|------|------|--------|
| `STEP2API_CONFIG_PATH` | 閰嶇疆鏂囦欢璺緞 | `config.json` |
| `STEP2API_CONFIG_JSON` | Base64缂栫爜鐨凧SON閰嶇疆 | - |
| `STEP2API_ADMIN_KEY` | Admin API Key | - |
| `STEP2API_HOST` | 鐩戝惉鍦板潃 | `127.0.0.1` |
| `STEP2API_PORT` | 鐩戝惉绔彛 | `5001` |
| `STEP2API_ACCOUNTS` | JSON鏍煎紡鐨勮处鍙峰垪琛?| - |
| `STEP2API_ACCOUNT_MAX_INFLIGHT` | 姣忚处鍙锋渶澶у苟鍙?| `2` |
| `STEP2API_ACCOUNT_MAX_QUEUE` | 绛夊緟闃熷垪涓婇檺 | `4` |

## 璁稿彲璇?
AGPL-3.0

鏈」鐩弬鑰冧簡 [ds2api](https://github.com/CJackHwang/ds2api) 鐨勬灦鏋勬€濊矾銆?