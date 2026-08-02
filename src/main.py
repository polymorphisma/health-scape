import sys
import logging
from src.scrapers.seek import SeekScraper
from src.scrapers.ethicaljobs import EthicalJobsScraper
from src.scrapers.jora import JoraScraper
from src.scrapers.workforceaustralia import WorkforceAustraliaScraper
from src.scrapers.indeed import IndeedScraper
from src.scrapers.careerone import CareerOneScraper
from src.scrapers.adzuna import AdzunaScraper
from src.processor import DataProcessor
from src.report import generate_report

SEEK_KEYWORDS = [
    'nurse',
    'aged care',
    'disability support',
    'allied health',
    'support worker',
]

ETHICALJOBS_KEYWORDS = [
    'nurse',
    'aged care',
    'disability support',
    'allied health',
]

JORA_KEYWORDS = [
    'nurse',
    'aged care',
    'disability support',
    'allied health',
    'support worker',
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('main')


def main():
    logger.info("=== Healthcare Job Scraper Starting ===")
    errors = []

    # 1. SEEK
    try:
        logger.info("--- Running SEEK scraper ---")
        seek = SeekScraper(base_dir=".")
        seek.run(SEEK_KEYWORDS)
        logger.info("SEEK scraper complete.")
    except Exception as e:
        logger.error(f"SEEK scraper failed: {e}", exc_info=True)
        errors.append(f"SEEK: {e}")

    # 2. EthicalJobs
    try:
        logger.info("--- Running EthicalJobs scraper ---")
        ej = EthicalJobsScraper(base_dir=".")
        ej.run(ETHICALJOBS_KEYWORDS)
        logger.info("EthicalJobs scraper complete.")
    except Exception as e:
        logger.error(f"EthicalJobs scraper failed: {e}", exc_info=True)
        errors.append(f"EthicalJobs: {e}")

    # 3. Jora
    try:
        logger.info("--- Running Jora scraper ---")
        jora = JoraScraper(base_dir=".")
        jora.run(JORA_KEYWORDS)
        logger.info("Jora scraper complete.")
    except Exception as e:
        logger.error(f"Jora scraper failed: {e}", exc_info=True)
        errors.append(f"Jora: {e}")

    # 4. WorkforceAustralia
    try:
        logger.info("--- Running WorkforceAustralia scraper ---")
        wfa = WorkforceAustraliaScraper(base_dir=".")
        wfa.run(JORA_KEYWORDS)
        logger.info("WorkforceAustralia scraper complete.")
    except Exception as e:
        logger.error(f"WorkforceAustralia scraper failed: {e}", exc_info=True)
        errors.append(f"WorkforceAustralia: {e}")

    # 5. Indeed AU
    try:
        logger.info("--- Running Indeed AU scraper ---")
        indeed = IndeedScraper(base_dir=".")
        indeed.run(JORA_KEYWORDS)
        logger.info("Indeed AU scraper complete.")
    except Exception as e:
        logger.error(f"Indeed scraper failed: {e}", exc_info=True)
        errors.append(f"Indeed: {e}")

    # 6. CareerOne
    try:
        logger.info("--- Running CareerOne scraper ---")
        c1 = CareerOneScraper(base_dir=".")
        c1.run(JORA_KEYWORDS)
        logger.info("CareerOne scraper complete.")
    except Exception as e:
        logger.error(f"CareerOne scraper failed: {e}", exc_info=True)
        errors.append(f"CareerOne: {e}")

    # 7. Adzuna AU
    try:
        logger.info("--- Running Adzuna AU scraper ---")
        adzuna = AdzunaScraper(base_dir=".")
        adzuna.run(JORA_KEYWORDS)
        logger.info("Adzuna scraper complete.")
    except Exception as e:
        logger.error(f"Adzuna scraper failed: {e}", exc_info=True)
        errors.append(f"Adzuna: {e}")

    # 9. Process + export
    try:
        logger.info("--- Running data processor ---")
        processor = DataProcessor(base_dir=".")
        output = processor.run()
        if output:
            logger.info(f"=== Pipeline complete. Output: {output} ===")
        else:
            logger.warning("Processor ran but produced no output.")
    except Exception as e:
        logger.error(f"Processor failed: {e}", exc_info=True)
        errors.append(f"Processor: {e}")

    # 10. Generate weekly summary report
    try:
        logger.info("--- Generating weekly summary report ---")
        report_path = generate_report(base_dir=".")
        if report_path:
            logger.info(f"Report: {report_path}")
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        errors.append(f"Report: {e}")

    if errors:
        logger.error(f"Completed with {len(errors)} error(s): {errors}")
        sys.exit(1)


if __name__ == "__main__":
    main()
