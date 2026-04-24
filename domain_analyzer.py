#!/usr/bin/env python3
"""
Domain Analyzer - Инструмент для анализа веб-сайтов
Проверяет реальные домены, находит ошибки и даёт рекомендации по:
- Cookie файлам
- Счётчикам аналитики
- Разметке страниц (Schema.org, Open Graph, meta-теги)
- SEO параметрам
- Производительности
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import sys
from urllib.parse import urlparse
from typing import Dict, List, Any


class DomainAnalyzer:
    def __init__(self, domain: str):
        self.domain = domain
        self.url = self._normalize_url(domain)
        self.html_content = None
        self.soup = None
        self.errors = []
        self.warnings = []
        self.info = []
        self.recommendations = []
        self.results = {
            'domain': domain,
            'url': self.url,
            'status': None,
            'cookies': {},
            'analytics': {},
            'meta_tags': {},
            'open_graph': {},
            'schema_org': [],
            'security': {},
            'issues': [],
            'recommendations': []
        }

    def _normalize_url(self, domain: str) -> str:
        """Нормализует домен в полный URL"""
        if not domain.startswith(('http://', 'https://')):
            return f'https://{domain}'
        return domain

    def fetch_page(self) -> bool:
        """Загружает страницу с домена"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            }
            
            response = requests.get(self.url, headers=headers, timeout=15, allow_redirects=True)
            response.encoding = response.apparent_encoding
            self.html_content = response.text
            self.results['status'] = {
                'code': response.status_code,
                'ok': response.status_code == 200
            }
            
            if response.status_code != 200:
                self.errors.append(f"Статус код: {response.status_code} вместо 200")
                return False
            
            self.soup = BeautifulSoup(self.html_content, 'html.parser')
            return True
            
        except requests.exceptions.Timeout:
            self.errors.append("Превышено время ожидания загрузки страницы")
            self.results['status'] = {'code': None, 'ok': False, 'error': 'timeout'}
            return False
        except requests.exceptions.ConnectionError:
            self.errors.append("Не удалось подключиться к домену")
            self.results['status'] = {'code': None, 'ok': False, 'error': 'connection_error'}
            return False
        except Exception as e:
            self.errors.append(f"Ошибка при загрузке: {str(e)}")
            self.results['status'] = {'code': None, 'ok': False, 'error': str(e)}
            return False

    def analyze_cookies(self):
        """Анализирует использование cookie"""
        # Проверяем заголовки Set-Cookie (если бы мы их получали через requests)
        # В реальном сценарии можно использовать session.cookies
        
        # Ищем упоминания cookie в JavaScript коде
        cookie_patterns = [
            r'document\.cookie',
            r'localStorage\.',
            r'sessionStorage\.',
            r'Cookie:',
            r'set-cookie',
            r'consent.*cookie',
            r'cookieConsent',
            r'GDPR.*cookie',
        ]
        
        cookies_found = []
        for pattern in cookie_patterns:
            matches = re.findall(pattern, self.html_content, re.IGNORECASE)
            if matches:
                cookies_found.extend(matches)
        
        if cookies_found:
            self.results['cookies']['usage_detected'] = True
            self.results['cookies']['patterns'] = list(set(cookies_found))[:10]
            self.info.append("Обнаружено использование cookie/хранилищ")
        else:
            self.results['cookies']['usage_detected'] = False
            self.warnings.append("Не обнаружено явного использования cookie")

        # Проверка на наличие уведомления о cookie
        cookie_banner_patterns = [
            r'cookie\s*banner',
            r'cookie\s*notice',
            r'cookie\s*consent',
            r'принять.*cookie',
            r'согласие.*cookie',
            r'gdpr',
            r'политика.*cookie',
        ]
        
        has_cookie_banner = False
        for pattern in cookie_banner_patterns:
            if re.search(pattern, self.html_content, re.IGNORECASE):
                has_cookie_banner = True
                break
        
        if has_cookie_banner:
            self.results['cookies']['banner_detected'] = True
            self.info.append("Обнаружено уведомление о cookie (требуется для GDPR)")
        else:
            self.results['cookies']['banner_detected'] = False
            self.warnings.append("Не найдено уведомления о cookie (может нарушать GDPR)")

    def analyze_analytics(self):
        """Анализирует наличие счётчиков аналитики"""
        analytics_trackers = {
            'Google Analytics': [r'googletagmanager\.com', r'google-analytics\.com', r'ga\.js', r'analytics\.js', r'gtag'],
            'Yandex Metrica': [r'metrica\.yandex\.ru', r'yandex\.ru/metrika', r'ym\(\d'],
            'Facebook Pixel': [r'facebook\.com/tr', r'fbq\(', r'facebook pixel'],
            'Google Tag Manager': [r'googletagmanager\.com/gtm'],
            'Hotjar': [r'hotjar\.com', r'hj\('],
            'LiveInternet': [r'liveinternet\.ru', r'counter\.liveinternet'],
            'Mail.ru Counter': [r'top\.mail\.ru', r'count\.mail\.ru'],
            'Bitrix24': [r'bitrix24\.'],
            'Roistat': [r'roistat\.com'],
            'Calltouch': [r'calltouch\.ru'],
        }
        
        found_analytics = []
        for name, patterns in analytics_trackers.items():
            for pattern in patterns:
                if isinstance(pattern, str):
                    if re.search(pattern, self.html_content, re.IGNORECASE):
                        found_analytics.append(name)
                        break
        
        self.results['analytics']['found'] = found_analytics
        
        if not found_analytics:
            self.warnings.append("Не найдено ни одного счётчика аналитики")
            self.recommendations.append("Добавьте Google Analytics или Яндекс.Метрику для отслеживания посетителей")
        else:
            self.info.append(f"Найдены счётчики: {', '.join(found_analytics)}")
        
        # Проверка на правильность установки GA4
        if 'Google Analytics' in found_analytics:
            if re.search(r'G-[A-Z0-9]{10}', self.html_content):
                self.info.append("GA4 настроен корректно (найден измерительный идентификатор)")
            elif re.search(r'UA-\d+-\d+', self.html_content):
                self.warnings.append("Используется Universal Analytics (устарел). Рекомендуется перейти на GA4")

    def analyze_meta_tags(self):
        """Анализирует meta-теги"""
        soup = self.soup
        
        # Основные meta-теги
        meta_checks = {
            'title': lambda: soup.find('title'),
            'description': lambda: soup.find('meta', attrs={'name': 'description'}),
            'keywords': lambda: soup.find('meta', attrs={'name': 'keywords'}),
            'viewport': lambda: soup.find('meta', attrs={'name': 'viewport'}),
            'charset': lambda: soup.find('meta', attrs={'charset': True}) or soup.find('meta', attrs={'http-equiv': 'Content-Type'}),
            'robots': lambda: soup.find('meta', attrs={'name': 'robots'}),
            'canonical': lambda: soup.find('link', attrs={'rel': 'canonical'}),
            'author': lambda: soup.find('meta', attrs={'name': 'author'}),
        }
        
        for tag_name, finder in meta_checks.items():
            element = finder()
            if element:
                if tag_name == 'title':
                    content = element.get_text(strip=True)
                    self.results['meta_tags'][tag_name] = {
                        'present': True,
                        'content': content,
                        'length': len(content)
                    }
                    if len(content) < 30:
                        self.warnings.append(f"Title слишком короткий ({len(content)} символов, рекомендуется 50-60)")
                    elif len(content) > 60:
                        self.warnings.append(f"Title слишком длинный ({len(content)} символов, рекомендуется 50-60)")
                elif tag_name == 'description':
                    content = element.get('content', '')
                    self.results['meta_tags'][tag_name] = {
                        'present': True,
                        'content': content,
                        'length': len(content)
                    }
                    if len(content) < 120:
                        self.warnings.append(f"Description слишком короткий ({len(content)} символов, рекомендуется 150-160)")
                    elif len(content) > 160:
                        self.warnings.append(f"Description слишком длинный ({len(content)} символов, рекомендуется 150-160)")
                else:
                    content = element.get('content', '') or element.get('href', '') or element.get('charset', '')
                    self.results['meta_tags'][tag_name] = {
                        'present': True,
                        'content': content
                    }
            else:
                self.results['meta_tags'][tag_name] = {'present': False}
                if tag_name in ['title', 'description', 'viewport', 'charset']:
                    self.errors.append(f"Отсутствует важный meta-тег: {tag_name}")
                    if tag_name == 'title':
                        self.recommendations.append("Добавьте тег <title> для улучшения SEO")
                    elif tag_name == 'description':
                        self.recommendations.append("Добавьте meta description для сниппетов в поиске")
                    elif tag_name == 'viewport':
                        self.recommendations.append("Добавьте viewport для мобильной адаптивности")

    def analyze_open_graph(self):
        """Анализирует Open Graph разметку"""
        og_tags = {}
        og_properties = ['og:title', 'og:description', 'og:image', 'og:url', 'og:type', 'og:site_name', 'og:locale']
        
        for prop in og_properties:
            element = self.soup.find('meta', property=prop)
            if element:
                og_tags[prop] = element.get('content', '')
        
        self.results['open_graph'] = og_tags
        
        required_og = ['og:title', 'og:description', 'og:image']
        missing_og = [tag for tag in required_og if tag not in og_tags]
        
        if missing_og:
            self.warnings.append(f"Отсутствуют важные Open Graph теги: {', '.join(missing_og)}")
            self.recommendations.append("Добавьте Open Graph разметку для красивых превью в соцсетях")
        else:
            self.info.append("Open Graph разметка присутствует")
        
        # Twitter Cards
        twitter_cards = self.soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')})
        if twitter_cards:
            self.results['twitter_cards'] = True
            self.info.append("Twitter Cards разметка обнаружена")
        else:
            self.results['twitter_cards'] = False
            self.warnings.append("Twitter Cards разметка отсутствует")

    def analyze_schema_org(self):
        """Анализирует Schema.org микроразметку"""
        schema_types = []
        
        # Поиск JSON-LD
        json_ld_scripts = self.soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    schema_type = data.get('@type', '')
                    if schema_type:
                        schema_types.append(schema_type)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            schema_type = item.get('@type', '')
                            if schema_type:
                                schema_types.append(schema_type)
            except (json.JSONDecodeError, AttributeError):
                continue
        
        # Поиск микроформатов в HTML
        schema_itemscope = self.soup.find_all(attrs={'itemscope': True})
        if schema_itemscope:
            for item in schema_itemscope:
                itemtype = item.get('itemtype', '')
                if itemtype:
                    schema_types.append(itemtype.split('/')[-1])
        
        self.results['schema_org'] = list(set(schema_types))
        
        if schema_types:
            self.info.append(f"Найдена Schema.org разметка: {', '.join(set(schema_types))}")
        else:
            self.warnings.append("Schema.org микроразметка не найдена")
            self.recommendations.append("Добавьте Schema.org разметку (Organization, LocalBusiness, Product и т.д.) для улучшения SEO")

    def analyze_performance(self):
        """Анализирует параметры производительности"""
        # Размер страницы
        page_size_kb = len(self.html_content.encode('utf-8')) / 1024
        self.results['performance'] = {
            'page_size_kb': round(page_size_kb, 2)
        }
        
        if page_size_kb > 500:
            self.warnings.append(f"Размер страницы большой: {round(page_size_kb, 2)} KB (рекомендуется < 500 KB)")
        else:
            self.info.append(f"Размер страницы: {round(page_size_kb, 2)} KB")
        
        # Количество внешних ресурсов
        external_scripts = self.soup.find_all('script', src=lambda x: x and x.startswith('http'))
        external_styles = self.soup.find_all('link', rel='stylesheet', href=lambda x: x and x.startswith('http'))
        
        self.results['performance']['external_scripts'] = len(external_scripts)
        self.results['performance']['external_styles'] = len(external_styles)
        
        if len(external_scripts) > 10:
            self.warnings.append(f"Много внешних скриптов: {len(external_scripts)} (может замедлять загрузку)")
        
        # Проверка на наличие lazy loading для изображений
        images = self.soup.find_all('img')
        lazy_images = [img for img in images if img.get('loading') == 'lazy']
        
        if images:
            lazy_ratio = len(lazy_images) / len(images)
            self.results['performance']['images_total'] = len(images)
            self.results['performance']['images_lazy'] = len(lazy_images)
            
            if lazy_ratio < 0.5 and len(images) > 5:
                self.warnings.append(f"Только {len(lazy_images)} из {len(images)} изображений используют lazy loading")
                self.recommendations.append("Добавьте loading='lazy' для изображений ниже первого экрана")

    def analyze_security(self):
        """Анализирует базовые параметры безопасности"""
        # Проверка на HTTPS
        if self.url.startswith('https://'):
            self.info.append("Сайт использует HTTPS")
        else:
            self.errors.append("Сайт не использует HTTPS")
            self.recommendations.append("Настройте HTTPS для безопасности данных пользователей")
        
        # Проверка Content Security Policy
        csp_meta = self.soup.find('meta', attrs={'http-equiv': 'Content-Security-Policy'})
        if csp_meta:
            self.info.append("Content Security Policy настроен")
            self.results['security']['csp'] = True
        else:
            self.warnings.append("Content Security Policy не найден")
        
        # Проверка на наличие форм без защиты
        forms = self.soup.find_all('form')
        insecure_forms = []
        for form in forms:
            action = form.get('action', '')
            if action and not action.startswith('https://') and not action.startswith('/'):
                insecure_forms.append(action)
        
        if insecure_forms:
            self.warnings.append(f"Найдены формы, отправляющие данные на небезопасные адреса: {insecure_forms[:3]}")

    def generate_report(self) -> Dict[str, Any]:
        """Генерирует итоговый отчёт"""
        self.results['errors'] = self.errors
        self.results['warnings'] = self.warnings
        self.results['info'] = self.info
        self.results['recommendations'] = self.recommendations
        
        # Подсчёт очков
        total_checks = len(self.errors) + len(self.warnings) + len(self.info)
        if total_checks > 0:
            score = int((len(self.info) / total_checks) * 100)
        else:
            score = 100
        
        self.results['score'] = max(0, min(100, score))
        
        return self.results

    def run_full_analysis(self) -> Dict[str, Any]:
        """Запускает полный анализ"""
        print(f"\n🔍 Анализ домена: {self.domain}")
        print("=" * 60)
        
        if not self.fetch_page():
            print(f"❌ Не удалось загрузить страницу: {self.url}")
            for error in self.errors:
                print(f"   • {error}")
            return self.generate_report()
        
        print(f"✅ Страница загружена (статус: {self.results['status']['code']})")
        
        print("\n📊 Выполняется анализ...")
        
        self.analyze_cookies()
        print("   ✓ Cookie файлы")
        
        self.analyze_analytics()
        print("   ✓ Счётчики аналитики")
        
        self.analyze_meta_tags()
        print("   ✓ Meta-теги")
        
        self.analyze_open_graph()
        print("   ✓ Open Graph")
        
        self.analyze_schema_org()
        print("   ✓ Schema.org")
        
        self.analyze_performance()
        print("   ✓ Производительность")
        
        self.analyze_security()
        print("   ✓ Безопасность")
        
        report = self.generate_report()
        
        print("\n" + "=" * 60)
        self.print_summary(report)
        
        return report

    def print_summary(self, report: Dict[str, Any]):
        """Выводит краткую сводку"""
        print(f"\n📈 ОБЩАЯ ОЦЕНКА: {report['score']}/100")
        
        if report['errors']:
            print(f"\n❌ ОШИБКИ ({len(report['errors'])}):")
            for error in report['errors']:
                print(f"   • {error}")
        
        if report['warnings']:
            print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЯ ({len(report['warnings'])}):")
            for warning in report['warnings']:
                print(f"   • {warning}")
        
        if report['info']:
            print(f"\n✅ НАЙДЕНО ({len(report['info'])}):")
            for info in report['info']:
                print(f"   • {info}")
        
        if report['recommendations']:
            print(f"\n💡 РЕКОМЕНДАЦИИ ({len(report['recommendations'])}):")
            for i, rec in enumerate(report['recommendations'], 1):
                print(f"   {i}. {rec}")


def main():
    if len(sys.argv) < 2:
        print("Использование: python domain_analyzer.py <домен>")
        print("Пример: python domain_analyzer.py example.com")
        print("Пример: python domain_analyzer.py https://mysite.ru")
        sys.exit(1)
    
    domain = sys.argv[1]
    analyzer = DomainAnalyzer(domain)
    report = analyzer.run_full_analysis()
    
    # Сохраняем отчёт в JSON файл
    output_file = f"analysis_{domain.replace('.', '_').replace('/', '_')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Полный отчёт сохранён в: {output_file}")


if __name__ == '__main__':
    main()
