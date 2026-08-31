from sentinel_app import FraudTriageService


def main():
    service = FraudTriageService()
    print(service.triage_account("A00985"))


if __name__ == "__main__":
    main()
