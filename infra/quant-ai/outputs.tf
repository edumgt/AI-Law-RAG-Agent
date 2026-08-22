output "ml_artifacts_bucket" {
  value       = aws_s3_bucket.ml_artifacts.bucket
  description = "app/config.py의 ML_ARTIFACTS_BUCKET에 넣을 값"
}

output "fund_web_instance_profile_name" {
  value       = aws_iam_instance_profile.fund_web.name
  description = "associate-iam-instance-profile 명령에 넣을 프로파일 이름"
}

output "quant_retrain_lambda_name" {
  value = aws_lambda_function.quant_retrain_trigger.function_name
}
