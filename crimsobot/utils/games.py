import mmap
import random
from collections import Counter
from datetime import datetime
from typing import List, Tuple, Union

import discord
from discord import Embed
from discord.ext import commands

from crimsobot.models.currency_account import CurrencyAccount
from crimsobot.models.guess_statistic import GuessStatistic
from crimsobot.models.wordle_results import WordleResults
from crimsobot.utils import tools as c

DiscordUser = Union[discord.User, discord.Member]


def get_crimsoball_answer(ctx: commands.Context) -> str:  # function to give first answer a ctx to work with
    # don't know if this is any better than just putting it
    # inside of the crimsoball command
    answer_list = [
            '{} haha ping'.format(ctx.message.author.mention),
            'ye!',
            '**no**',
            'what do you think?',
            '*perhaps*',
            'OMAN',
            "i can't answer this, you need an adult",
            'absolutely!\n\n\n`not`',
            'of course!',
            'according to quantum superposition, the answer was both yes and no before you asked.',
            "is the sky blue?\n\n(is it? i don't know. i don't have eyes.)",
            "i can't be bothered with this right now.",
            'funny you should ask--',
            'fine, sure, whatever',
            '<:xok:551174281367650356>',
            'ask seannerz. ping him now and ask.',
            'ehhhh sure',
            'hmmmm. no.',
            'uhhhhhhhhh',
            '<:uhhhh:495249068789071882>',
            'eat glass!',
            'it is important that you stop bothering me.',
            'you CANNOT be serious',
            'sure? how would i know?',
            'what heck',
            'random_response',  # leave this alone
        ]

    return random.choice(answer_list)


def emojistring() -> str:
    emojis = []
    for line in open(c.clib_path_join('games', 'emojilist.txt'), encoding='utf-8', errors='ignore'):
        line = line.replace('\n', '')
        emojis.append(line)

    emoji_string = random.sample(''.join(emojis), random.randint(3, 5))

    return ' '.join(emoji_string)


def tally(ballots: List[str]) -> Tuple[str, int]:
    counter = Counter(sorted(ballots))
    winner = counter.most_common(1)[0]

    return winner


def winner_list(winners: List[str]) -> str:
    if len(winners) > 1:
        winners_ = ', '.join(winners[:-1])
        winners_ = winners_ + ' & ' + winners[-1]  # winner, winner & winner
    else:
        winners_ = winners[0]

    return winners_


async def win(discord_user: DiscordUser, amount: float) -> None:
    account = await CurrencyAccount.get_by_discord_user(discord_user)  # type: CurrencyAccount
    account.add_to_balance(amount)
    await account.save()


async def daily(discord_user: DiscordUser, lucky_number: int) -> Embed:
    # fetch account
    account = await CurrencyAccount.get_by_discord_user(discord_user)  # type: CurrencyAccount

    # get current time
    now = datetime.utcnow()

    # arbitrary "last date collected" and reset time (midnight UTC)
    reset = datetime(1969, 7, 20, 0, 0, 0)  # ymd required but will not be used

    last = account.ran_daily_at

    # check if dates are same; if so, gotta wait
    if last and last.strftime('%Y-%m-%d') == now.strftime('%Y-%m-%d'):
        hours = (reset - now).seconds / 3600
        minutes = (hours - int(hours)) * 60

        title = 'Patience...'
        award_string = 'Daily award resets at midnight UTC, {}h{}m from now.'.format(int(hours), int(minutes + 1))
        thumb = 'clock'
        color = 'orange'
    # if no wait, then check if winner or loser
    else:
        winning_number = random.randint(1, 100)

        if winning_number == lucky_number:
            daily_award = 500

            title = 'JACKPOT!'
            wrong = ''  # they're not wrong!
            thumb = 'moneymouth'
            color = 'green'

        else:
            daily_award = 10

            title_choices = [
                '*heck*',
                '*frick*',
                '*womp womp*',
                '**😩**',
                'Aw shucks.',
                'Why even bother?',
            ]
            title = random.choice(title_choices)
            wrong = 'The winning number this time was **{}**, but no worries:'.format(winning_number)
            thumb = 'crimsoCOIN'
            color = 'yellow'

        # update daily then save
        account.ran_daily_at = now
        await account.save()

        # update their balance now (will repoen and reclose user)
        await win(discord_user, daily_award)

        award_string = '{} You have been awarded your daily **\u20A2{:.2f}**!'.format(wrong, daily_award)
        thumb = thumb
        color = color

    # the embed to return
    embed = c.crimbed(
        title=title,
        descr=award_string,
        thumb_name=thumb,
        color_name=color,
    )
    return embed


async def check_balance(discord_user: DiscordUser) -> float:
    account = await CurrencyAccount.get_by_discord_user(discord_user)  # type: CurrencyAccount

    return account.get_balance()


def guess_economy(n: int) -> Tuple[float, float]:
    """ input: integer
       output: float, float"""

    # winnings for each n=0,...,20
    winnings = [0, 7, 2, 4, 7, 11, 15, 20, 25, 30, 36, 42, 49, 56, 64, 72, 80, 95, 120, 150, 200]

    # variables for cost function
    const = 0.0095  # dampener multiplier
    sweet = 8  # sweet spot for guess
    favor = 1.3  # favor to player (against house) at sweet spot

    # conditionals
    if n > 2:
        cost = winnings[n] / n - (-const * (n - sweet) ** 2 + favor)
    else:
        cost = 0.00

    return winnings[n], cost


async def guess_luck(discord_user: DiscordUser, n: int, won: bool) -> None:
    stats = await GuessStatistic.get_by_discord_user(discord_user)  # type: GuessStatistic

    stats.plays += 1
    stats.add_to_expected_wins(n)
    if won:
        stats.wins += 1

    await stats.save()


# async def guess_luck_balance(discord_user: DiscordUser) -> Tuple[float, int]:
#     stats = await GuessStatistic.get_by_discord_user(discord_user)  # type: GuessStatistic

#     return stats.luck_index, stats.plays

async def guess_stat_embed(user: DiscordUser) -> Embed:
    """Return a big ol' embed of Guessmoji! stats"""

    s = await GuessStatistic.get_by_discord_user(user)

    if s.plays == 0:
        embed = c.crimbed(
            title='HOW—',
            descr="You haven't played GUESSMOJI! yet!",
            thumb_name='weary',
            footer='Play >guess [n] today!',
        )
    else:
        embed = c.crimbed(
            title='GUESSMOJI! stats for {}'.format(user),
            descr=None,
            thumb_name='crimsoCOIN',
            footer='Stat tracking as of {d.year}-{d.month:02d}-{d.day:02d}'.format(d=s.created_at),
        )

        ess = '' if s.plays == 1 else 's'
        ess2 = '' if s.wins == 1 else 's'

        # list of tuples (name, value) for embed.add_field
        field_list = [
            (
                'Gameplay',
                '**{}** game{ess} played, **{}** win{ess2}'.format(s.plays, s.wins, ess=ess, ess2=ess2)
            ),
            (
                'Luck index (expected: 100)',
                '**{:.3f}**'.format(100 * s.luck_index)
            ),
        ]

        for field in field_list:
            embed.add_field(name=field[0], value=field[1], inline=False)

    return embed


def guesslist() -> str:
    output = [' n  ·   cost   ·   payout',
              '·························']
    for i in range(2, 21):
        spc = '\u2002' if i < 10 else ''
        w, c = guess_economy(i)
        output.append('{}{:>d}  ·  \u20A2{:>5.2f}  ·  \u20A2{:>6.2f}'.format(spc, i, c, w))

    return '\n'.join(output)


# -----Wordle-----

# emoji match indicators
no_match = '❌'
in_word = '🟨'
exact_match = '🟩'

# the possible solutions
wordfile_path = c.clib_path_join('games', 'five-letter-words.txt')


async def choose_solution() -> str:
    """Choose a random five-letter word from the plaintext file.

    Word list: https://www-cs-faculty.stanford.edu/~knuth/sgb-words.txt

    Approach used: https://stackoverflow.com/a/35579149"""

    line_num = 0
    selected_line = ''

    with open(wordfile_path, encoding='utf-8', errors='ignore') as f:
        while True:
            line = f.readline()
            if not line:
                break
            line_num += 1
            if random.uniform(0, line_num) < 1:
                selected_line = line

    word = selected_line.strip()

    return word


async def input_checker(user_guess: str) -> bool:
    """Check if the user's input is actually a word.

    Method for checking if input is in text file: https://stackoverflow.com/a/4944929"""

    if len(user_guess) != 5:
        valid = False
    else:
        with open(wordfile_path, encoding='utf-8', errors='ignore') as f, \
                mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as s:
            if s.find(str.encode(user_guess)) != -1:
                valid = True
            else:
                valid = False

    return valid


async def match_checker(user_guess: str, solution: str) -> Tuple[List[str], str, str]:
    """Check user input against solution"""

    user_matches = [no_match] * 5  # start fresh
    in_solution = ''

    def remove_letter(guess_or_solution: str, index: int, replace_with: str) -> str:
        """Remove a letter to exclude from further matching"""
        temp_list = list(guess_or_solution)  # str to list to make assignment possible
        temp_list[index] = replace_with  # some non-letter symbol
        guess_or_solution = ''.join(temp_list)

        return guess_or_solution

    # check first exclusively for exact matches...
    for idx_in, letter_in in enumerate(user_guess):
        for idx_sol, letter_sol in enumerate(solution):
            if letter_in == letter_sol:
                if idx_in == idx_sol:
                    user_matches[idx_in] = exact_match
                    in_solution += letter_in

                    # remove from both
                    user_guess = remove_letter(user_guess, idx_in, '*')
                    solution = remove_letter(solution, idx_sol, '&')

    # ...then for partial matches
    for idx_in, letter_in in enumerate(user_guess):
        for idx_sol, letter_sol in enumerate(solution):
            if letter_in == letter_sol:
                user_matches[idx_in] = in_word
                in_solution += letter_in

                # remove from both
                user_guess = remove_letter(user_guess, idx_in, '*')
                solution = remove_letter(solution, idx_sol, '&')

    # get a string of letters not in solution
    not_in_solution = user_guess

    for letter in in_solution:
        not_in_solution = not_in_solution.replace(letter, '')

    return user_matches, in_solution, not_in_solution


async def remaining_letters(right_guesses: str, wrong_guesses: str) -> List[str]:
    """Return a list of letters that are still available."""

    alphabet = 'abcdefghi\njklmnopqr\nstuvwxyz'

    remaining_alphabet = []  # list of strings to be represented as emojis

    for letter in alphabet:
        if letter in right_guesses:
            char_to_append = f'[{letter}]'
        elif letter in wrong_guesses:
            char_to_append = ' · '
        elif letter == '\n':
            char_to_append = letter
        else:
            char_to_append = f' {letter} '

        remaining_alphabet.append(char_to_append)

    return remaining_alphabet


async def wordle_stats(discord_user: DiscordUser, guesses: int, word: str) -> None:
    stats = await WordleResults.create_result(discord_user)  # type: WordleResults

    stats.guesses = guesses
    stats.word = word

    await stats.save()
