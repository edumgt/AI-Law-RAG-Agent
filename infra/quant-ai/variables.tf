variable "region" {
  description = "AWS region — 실제 운영 EC2(fund-web)가 있는 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
  default     = "086015456585"
}

variable "fund_web_instance_id" {
  description = "Comprehend/S3 접근용 IAM 인스턴스 프로파일을 붙일 대상 EC2 인스턴스 ID"
  type        = string
  default     = "i-0aaa5e2b46133573b"
}

# SageMaker 사전빌드 scikit-learn 프레임워크 컨테이너 URI.
# aws/sagemaker-python-sdk 레포의 sagemaker-core/src/sagemaker/core/image_uri_config/sklearn.json
# training.versions["1.2-1"].registries["ap-northeast-2"] = "366743142698"로 확인함 (2026-08-22).
variable "sagemaker_sklearn_image" {
  description = "SageMaker scikit-learn framework container image URI (region/account 확인 필수)"
  type        = string
  default     = "366743142698.dkr.ecr.ap-northeast-2.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3"
}
