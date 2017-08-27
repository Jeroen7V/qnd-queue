
# Introduction


# Installation


# First run

```
curl -i http://localhost:8888/install?username=test&password=test
```

# Usage - API Calls

## Authentication
```
# User authentication
$user = 'demo1'
$pass = 'demo1'
$pair = "$($user):$($pass)"
$encodedCreds = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes($pair))
$basicAuthValue = "Basic $encodedCreds"
$Headers = @{
    Authorization = $basicAuthValue
} 
```
## - GET: /api/version
```
# Get the API version (see if it is working)
$page = Invoke-RestMethod -Uri http://localhost/api/version

Write-Output "API version: "$page.version 

```


## - GET: /api/token
```
Invoke-RestMethod -Headers $Headers -Uri http://localhost/api/clear/demo1_q1
```


## - POST: /api/msg/<string:queue>
```
# Post to MQ
Invoke-RestMethod -Headers $Headers -Uri http://localhost/api/msg/demo1_q1 -Method POST -Body (ConvertTo-Json "THIS IS MY TEXT") -ContentType "application/json"
```
## - GET: /api/msg/<string:queue>
```
Write-Output "All messages in demo1_q1"
# Make a call to msg queue

$page = Invoke-RestMethod -Headers $Headers -Uri http://localhost/api/msg/demo1_q1

for ($i=0;$i -lt $page.messages.Length; $i++) {
    $page.messages[$i]
} 
```

## - DELETE: /api/msg/<int:id>
```
# Delete a message from the MQ
$id = 1
Write-Output "Deleting message with an id of $id" 

$url = "http://localhost/api/msg/$id"
Invoke-RestMethod -Headers $Headers -Uri $url -Method DELETE

```

## - GET: /api/clear/<string:queue>

```
Invoke-RestMethod -Headers $Headers -Uri http://localhost/api/clear/demo1_q1
```


## - GET: /api/truncate/<string:queue>

```
Invoke-RestMethod -Headers $Headers -Uri http://localhost/api/truncate/demo1_q1
```
