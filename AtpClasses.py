from selenium import webdriver, common
import mysql.connector
import config
import re


class AtpScores:
    def __init__(self, tournament):
        self._driver = None
        self._tournament = tournament
        self.url = tournament.url_score
        self.score = None
        self.winner = None
        self.loser = None
        self.round = None
        self.url_players = []
        self.url_detail = None
        self.id = None
        self._KO_count = 0
        self._win = None

    def reset(self):
        """ Reset the object keeping driver and url and KO_count and round"""
        self.score = None
        self.winner = None
        self.loser = None
        self.url_players = []
        self.url_detail = None
        self.id = None
        self._win = None

    def _set_round(self, selenium_object):
        """ Scrap data about the score from selenium object ('head')"""
        try :
            self.round = selenium_object.find_element_by_tag_name('th').text
        except common.exceptions.NoSuchElementException:
            self.round = None

    def _set_scores_info(self, selenium_object):
        try:
            self.winner = selenium_object.find_elements_by_class_name('day-table-name')[0].text
            self.url_players.append((selenium_object.find_elements_by_class_name('day-table-name')[0] \
                .find_element_by_tag_name('a').get_attribute('href'), 1))  # URL - WINNER
            self.loser = selenium_object.find_elements_by_class_name('day-table-name')[1].text
            self.url_players.append((selenium_object.find_elements_by_class_name('day-table-name')[1] \
                .find_element_by_tag_name('a').get_attribute('href'), 0))  # Url - Losers
            self.score = selenium_object.find_element_by_class_name('day-table-score').text
            self.url_detail = selenium_object.find_element_by_class_name('day-table-button') \
                .find_element_by_tag_name('a').get_attribute('href')
        except common.exceptions.NoSuchElementException:
            self.winner = self.url_winner = self.loser = self.url_loser = self.score = self.url_detail = None

    def _check_game_exist(self): pass

    def _save_into_games(self):
        cursor = config.CON.cursor()
        try:
            print(self._tournament.id)

            cursor.execute(''' insert into games (tournament_id,score,round)
                                values(%s,%s,%s)''',
                           [self._tournament.id, self.score,
                            self.round])
            config.logging.info(f"Added Score from round {self.round} of {self._tournament.name} "
                                f"between {self.winner} and {self.loser} into the DB")
            self.id = cursor.lastrowid
            config.CON.commit()
        except (mysql.connector.IntegrityError, mysql.connector.DataError) as e:
            config.logging.error(f"Failed to add score from round {self.round} of {self._tournament.name} "
                                 f"between {self.winner} and {self.loser} into the DB")
        cursor.close()

    def _save_into_games_players(self, player):
        cursor = config.CON.cursor()
        try:
            cursor.execute(''' insert into games_players (player_id, game_id, won)
                                values(%s, %s, %s)''',
                           [player.id, self.id,
                            self._win])
            config.logging.info(f"Added new row in games_players player_id:{player.id}, game_id:{self.id} "
                                f"between {self.winner} and {self.loser} into the DB")
            config.CON.commit()
        except (mysql.connector.IntegrityError, mysql.connector.DataError) as e:
            config.logging.error(f"Failed to add new row in games_players player_id:{player.id}, game_id:{self.id}"
                                 f" into the games_players table")
            print([player.id, self.id,
                            self._win])
        cursor.close()

    def _save_into_database(self, player):
        # Input data into players table if needed
        if player.check_player_exist(): # IN DB
            player.get_from_table()
        else: # not in DB
            player.save_into_table()
        # Into game_players
        self._save_into_games_players(player)

    def scores_tournament_data(self, test=False):
        """
        Extract general information about tournament of a particular year from ATP
        """
        atp_table = []
        # start_time = time.time()
        driver = webdriver.Chrome(config.PATH)
        driver.get(self.url)
        self._driver = driver
        table = self._driver.find_element_by_class_name('day-table')
        tbody = table.find_elements_by_tag_name('tbody')
        thead = table.find_elements_by_tag_name('thead')
        for head, body in zip(thead, tbody):
            self._set_round(head)
            tr_l = body.find_elements_by_tag_name('tr')

            for tr in tr_l:
                self.reset( )
                self._set_scores_info(tr)
                print(f"Scrapping {self.round} between {self.winner} and {self.loser}")
                # Save into games
                self._save_into_games()
                # Save into games_players and players
                for url_player in self.url_players:
                    player = AtpPlayer(url_player[0]).get_player_info()
                    self._win = url_player[1]
                    self._save_into_database(player=player)
                if test: break
        # Close driver
        self._driver.close()


class AtpPlayer:
    def __init__(self, player_url):
        self.firstname = None
        self.lastname = None
        self.ranking_sgl = None
        self.ranking_dbl = None
        self.career_high_sgl = None
        self.career_high_dbl = None
        self.country = None
        self.date_birth = None
        self.turned_pro = None
        self.weight = None
        self.height = None
        self.total_prize_money = None
        self.player_url = player_url
        self._driver = None
        self.id = None

    def get_from_table(self):
        """ Get player id from the player table."""
        cursor = config.CON.cursor()
        print((self.firstname, self.lastname))
        cursor.execute("select player_id from players where first_name = %s "
                       "and last_name = %s ", [self.firstname, self.lastname])
        self.id = cursor.fetchall()[0][0]
        cursor.close()

    def save_into_table(self):
        cursor = config.CON.cursor()
        try:
            cursor.execute(''' insert into players (first_name,last_name,ranking_DBL,ranking_SGL,
                        career_high_DBL,career_high_SGL,turned_pro, weight,height, total_prize_money, country, birth)
                        values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ''',
                           [self.firstname, self.lastname,
                            self.ranking_dbl, self.ranking_sgl, self.career_high_dbl,
                            self.career_high_sgl, self.turned_pro, self.weight, self.height,
                            self.total_prize_money, self.country, self.date_birth])
            config.logging.info(f"Added {self.firstname} {self.lastname} into the DB")
            self.id = cursor.lastrowid
            config.CON.commit()
        except (mysql.connector.IntegrityError, mysql.connector.DataError) as e:
            config.logging.error(
                f"Failed to enter player {self.firstname} {self.lastname} details into the DB- {e}")
            print( f"Failed to enter player {self.firstname} {self.lastname} details into the DB- {e}")
            self.id = None
        cursor.close()

    def check_player_exist(self):
        """ Check if players information exist in db. """

        self.firstname = self.player_url.split('/')[5].split('-')[0]
        self.lastname = self.player_url.split('/')[5].split('-')[1]

        # check if player exists in the DB
        cursor = config.CON.cursor()
        cursor.execute("select player_id from players where first_name = %s "
                       "and last_name = %s ", [self.firstname, self.lastname])

        check_exist = cursor.fetchall()
        # print(f"check -- {check_exist[0][0]} -----")
        if len(check_exist)>0: # Player exists in db
            config.logging.info(f"{self.firstname} {self.lastname} already exists in players table.")
            print(f"{self.firstname} {self.lastname} already exists in players table.")
            self.id = check_exist[0][0]
            cursor.close()
            return True
        else:
            cursor.close()
            return False

    def _set_player_ranking(self):
        try:
            self.ranking_sgl = int(self._driver.find_elements_by_class_name('stat-value')[0].get_attribute(
                'data-singles'))  # current ranking- singles
           # print(self.ranking_sgl)
            self.ranking_dbl = int(self._driver.find_elements_by_class_name('stat-value')[0].get_attribute(
                'data-doubles'))  # current ranking- doubles
           # print(self.ranking_dbl)
        except Exception:
            ranking_sgl = None
            ranking_dbl = None
            config.logging.warning("couldn't find player's singles/doubles ranking..")

    def _set_player_highest_ranking(self):
        self.career_high_sgl = int(self._driver.find_elements_by_class_name('stat-value')[5].get_attribute(
            'data-singles'))  # career high ranking- singles
        #print(career_high_sgl)
        self.career_high_dbl = int(self._driver.find_elements_by_class_name('stat-value')[5].get_attribute(
            'data-doubles'))  # career high ranking- doubles
        #print(career_high_dbl)

    def _set_player_country(self):
        try:
            self.country = self._driver.find_element_by_class_name('player-flag-code').text  # country
            # print(self.country)
        except Exception:
            self.country = None
            config.logging.warning("couldn't find player's country..")

    def _set_player_datebirth(self):
        try:
            self.date_birth = self._driver.find_element_by_class_name('table-birthday').text.strip('()')  # date of birth
           # print(self.date_birth)
        except Exception:
            self.date_birth = None
            config.logging.warning("couldn't find player's date of birth..")

    def _set_player_turnedpro(self):
        try:
            self.turned_pro = int(self._driver.find_elements_by_class_name('table-big-value')[1].text)  # turned pro
            # print(self.turned_pro)
        except Exception:
            self.turned_pro = None
            config.logging.warning("couldn't find the date the player turned pro..")

    def _set_player_weight_height(self):
        try:
            self.weight = float(self._driver.find_element_by_class_name('table-weight-lbs').text)  # weight
            #print(self.weight)

            self.height = float(self._driver.find_element_by_class_name('table-height-cm-wrapper').text[1:4])  # height
            # print(self.height)
        except Exception:
            self.weight = None
            self.height = None
            config.logging.warning("couldn't find player's height\weight..")

    def _set_player_total_prize(self):
        try:
            self.total_prize_money = int(
                self._driver.find_elements_by_class_name('stat-value')[8].text.split()[0][1:].replace(',',
                                                                                                ''))  # total prize money
           # print(self.total_prize_money)
        except Exception:
            self.total_prize_money = None
            config.logging.warning("couldn't find player's total prize money earnings..")

    def get_player_info(self):
        """ Get players information from their profiles """

        # check if player exists in the DB
        if self.check_player_exist(): return self # if player does exist in DB
        # connect to ChromeDriver
        driver = webdriver.Chrome(config.PATH)
        driver.get(self.player_url)
        self._driver = driver

        print("Getting info about {} {}".format(self.firstname, self.lastname))
        self._set_player_ranking() # Player ranking
        self._set_player_highest_ranking() # Player highest ranking
        self._set_player_country() # Player country
        self._set_player_datebirth() # Player date of birth
        self._set_player_turnedpro() # Player turned pro
        self._set_player_weight_height() # Player weight height
        self._set_player_total_prize() # Player total_prize
        self._driver.close()
        return self


class AtpScrapper:

    def __init__(self,new_tourn_type):
        self.year = None
        self.location = None
        self.date = None
        self.name = None
        self.draw_singles = None
        self.new_tourn_type = new_tourn_type
        self.draw_doubles= None
        self.surface = None
        self.prize_money = None
        self.url_score = None
        self.single_winner = None
        self.double_winner = None
        self._driver = None
        self._url_winner = list()
        self.players = None
        self.id = None
        self.type = None
        self._score = None

    def reset(self):
        """ Reset the object keeping _driver, year and tournament_type """
        self.location = None
        self.date = None
        self.name = None
        self.draw_singles = None
        self.draw_doubles= None
        self.surface = None
        self.prize_money = None
        self.url_score = None
        self.single_winner = None
        self.double_winner = None
        self._url_winner = list()
        self.id = None
        self.type = None

    def _connexion(self, url):
        """ return a selenium object containing the page of the input url."""
        driver = webdriver.Chrome(config.PATH)
        driver.get(url)
        year = re.findall(r'year=([0-9]{4})', url)[0]
        self.year = year
        print(f"scraping results from year {year}..")
        self._driver = driver

    def _set_tournament_type(self, selenium_obj):
        """ Output the tournament type from a selenium object input"""
        try:  # find which type of tournament it is- 250, 500, 1000, grand slam, finals?
            td_class = selenium_obj.find_element_by_class_name('tourney-badge-wrapper')
            tourn_type = td_class.find_element_by_tag_name('img').get_attribute('src')
            new_tourn_type = tourn_type.split('_')[1].split('.')[0]
        except common.exceptions.NoSuchElementException:
            new_tourn_type = 'NA'
            config.logging.warning("Couldn't find tournament's type")
        self.new_tourn_type = new_tourn_type

    def _set_tournament_title_content(self, selenium_object):
        """ Set the name, location and date of the tournament from a selenium object input ('title-content') """
        td_content = selenium_object.find_element_by_class_name('title-content')  # basic details- name, location,dates
        self.name = td_content.find_element_by_class_name('tourney-title').text  # tournament's name
        self.location = td_content.find_element_by_class_name('tourney-location').text  # tournament's location
        self.dates = td_content.find_element_by_class_name('tourney-dates').text  # tournament's dates

    def _set_tournament_detail(self, selenium_object):
        """ Set draw_singles, doubles, and surface, prize_money from a selenium object input ('tourney-detail)"""
        td_draw = selenium_object.find_elements_by_class_name('tourney-details')  # number of participants in the draw
        self.draw_singles = int(td_draw[0].find_elements_by_tag_name('span')[0].text)  # singles- draw
        self.draw_doubles = int(td_draw[0].find_elements_by_tag_name('span')[1].text)  # doubles- draw
        self.surface = td_draw[1].text  # surface type
        try:
            self.prize_money = int(td_draw[2].text[1:].replace(',', ''))  # prize money
        except:
            self.prize_money = None
            config.logging.error("couldn't get tournament's prize money")

    def _set_url_scores(self, selenium_object):
        """
        Takes a selenium class object (selenium.webdriver.remote.webelement.WebElement) of an atp website and extract
        the url to a webpage with detail results of each tournament. Return NA if it does not find the tag.
        """
        try:
            self.url_score = selenium_object.find_element_by_class_name('button-border').get_attribute('href')
        except common.exceptions.NoSuchElementException:
            self.url_score = 'NA'

    def _set_winner(self, selenium_object):
        """ Set winner from selenium object - (tourney-detail-winner)"""
        winners = selenium_object.find_elements_by_class_name('tourney-detail-winner') # winners
        self._url_winner = []
        # get the tournament winners:
        for winner in winners:
            if 'SGL: ' in winner.text:
                self.single_winner = winner.text.split(': ')[1]
                self._url_winner.append((winner.find_element_by_tag_name('a').get_attribute('href'), 'SGL'))
            elif 'DBL: ' in winner.text:
                self.double_winner = winner.text.split(': ')[1]
                self._url_winner.append((winner.find_elements_by_tag_name('a')[0].get_attribute('href'), 'DBL'))
                self._url_winner.append((winner.find_elements_by_tag_name('a')[1].get_attribute('href'), 'DBL'))
                self.type = 'DBL'

    def _save_into_table_champion(self, player):
        cursor = config.CON.cursor()
        try:
            cursor.execute(''' insert into champions (player_id,tournament_id,type) 
                            values(%s,%s,%s)''',
                           [player.id, self.id,
                            self.type])
            self.id = cursor.lastrowid
            config.logging.info(f"Updated champions table successfully!")
        except (mysql.connector.IntegrityError, mysql.connector.DataError) as e:
            config.logging.error(f'Error when trying to update champions for - {self.name}: {e}')
        config.CON.commit()
        cursor.close()

    def _save_into_table(self):
        """  Save tournament information into the tournament table"""
        cursor = config.CON.cursor()
        try:
            cursor.execute(''' insert into tournaments (year,type,name,location,date,SGL_draw,
                DBL_draw, surface, prize_money) values(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                           [self.year, self.new_tourn_type,
                            self.name, self.location, self.dates,
                            self.draw_singles,
                            self.draw_doubles,
                            self.surface, self.prize_money])
            self.id = cursor.lastrowid
            config.logging.info(f"Scraped tournament {self.name} - {self.year} and updated DB successfully!")
        except (mysql.connector.IntegrityError, mysql.connector.DataError) as e:
            config.logging.error(f'Error when trying to insert tournament- {self.name}: {e}')
        config.CON.commit()
        cursor.close()

    def _save_into_database(self, player=None):
        """Save all information scrapped in the database."""
        check_exist = player.check_player_exist()
        # Save player information
        if (self.players) & (check_exist is False):  # player is not in DB
            player.save_into_table()
            self._save_into_table_champion(player)
        elif (self.players) & (check_exist):  # Player is already in db
            player.get_from_table()
            self._save_into_table_champion(player)

    def _check_tournament_exist(self):
        """ check if tournament exists in DB  """

        cursor = config.CON.cursor()
        cursor.execute("select tournament_id from tournaments where name = %s "
                       "and year = %s ", [self.name, self.year])  # check if tournament exist in DB,
        check_exist = cursor.fetchall()
        cursor.close()
        if len(check_exist) > 0:  # if tournament does exist
            config.logging.info(f'''This tournament: {self.name} - {self.year} was already scraped before, and is '
                                        already located in the DB''')
            self.id = check_exist[0][0]
            print(f'''This tournament: {self.name} - {self.year} was already scraped before, and is '
                                        already located in the DB''')
            return True

    def tournament_data(self, url, score=None, winner=None, test=False):
        """Go through the url page, get information on each tournament and save them in tournament table inside
        web_scraping_project db
        url - url to scrap
        score = if True scrap all scores of each tournament
        players - if 'winner' scrap information about winners of each tournament.
                  if 'all' scrap information about each player of the tournament
                """
        player = None
        self.players = winner
        self._score = score
        self._connexion(url)
        table = self._driver.find_element_by_id('scoresResultsArchive')
        tr = table.find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')
        # config.logging.info(f'Scraping results from year {url}. scraping {filter} tournaments.')
        for count,i in enumerate(tr):  # each 'tr' tag holds the relevant information regarding each tournament in the URL
            self.reset()
            print("{:.2f} done for the year {}".format(count/len(tr), self.year))
            if self.new_tourn_type is None:
                self._set_tournament_type(i)  # Tournament Type
            self._set_tournament_title_content(i)  # Set name, location, dates from title-content
            # Check if tournament exists in db:
            config.logging.info(f'Scraping tournament of type: {self.new_tourn_type}')
            self._set_tournament_detail(i)  # Set draw, single, double, surface and prize_money
            self._set_url_scores(i)  # Set url of tournament scores WE DON'T USE IT YET
            self._set_winner(i)  # Set winner_single, and winner_double, if they exist
            # Save tournament information if needed
            if not self._check_tournament_exist():
                self._save_into_table()
            if winner:
                for url in self._url_winner:  # len()=1 : One single winner, =3 : Single and double winners ...
                    self.type = url[1]
                    player = AtpPlayer(url[0]).get_player_info()
                    print(f"New player {player.lastname} {player.firstname}")
                    print(f"urls list ---- {self._url_winner}")
                    self._save_into_database(player=player)
            print('score: {}'.format(score))
            if score:
                atpscore = AtpScores(self)
                atpscore.scores_tournament_data()
            # if test: break
        self._driver.close()
        config.logging.info(f'Finished scraping {url}')







