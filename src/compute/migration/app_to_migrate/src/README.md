# Useful commands
sudo systemctl status app
sudo systemctl restart app

# Debug

## Log

Check the *.log

## Start the program manually
./start.sh
ps -ef |grep python

## Curl
curl -X POST -H "Content-Type: application/json" -d '{ "text": "What are the company policies on remote work?", "max_tokens": 1000, "temperature": 0 }' http://localhost:3000/cohere/generate

curl -X POST -H "Content-Type: application/json" -d '{ "text": "What are the company policies on remote work?", "max_tokens": 1000, "temperature": 0 }' https://xxxxxx.apigateway.eu-frankfurt-1.oci.customer-oci.com/cohere/generate

## Test connectivity from ADB
declare
  req utl_http.req;
  res utl_http.resp;
  buffer varchar2(4000); 
  url varchar2(4000); --  'https://xxxx.apigateway.eu-frankfurt-1.oci.customer-oci.com/cohere/generate'
  content varchar2(4000) := '{ "text": "What are the company policies on remote work?", "max_tokens": 1000, "temperature": 0 }';
begin
  select value into url from DEMO_UK_AI_SANDBOX_SETTINGS where setting='VM Address';
  dbms_output.put_line('URL : ' || url);
  req := utl_http.begin_request(url, 'POST',' HTTP/1.1');
  utl_http.set_header(req, 'user-agent', 'mozilla/4.0'); 
  utl_http.set_header(req, 'content-type', 'application/json'); 
  utl_http.set_header(req, 'Content-Length', length(content));
  utl_http.write_text(req, content);
  res := utl_http.get_response(req);
  if (res.status_code = UTL_HTTP.HTTP_OK) then
    dbms_output.put_line('Success: Received OK response');
    begin
      loop
          utl_http.read_line(res, buffer);
          dbms_output.put_line(buffer);
      end loop;
    exception
     when UTL_HTTP.end_of_body then
       UTL_HTTP.end_response(res);
    end;         
  else
    dbms_output.put_line ('Failure: Received non-OK response: ' ||res.status_code||' '||res.reason_phrase);
  end if;    
end;
/