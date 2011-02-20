#!/usr/bin/env python
#
# OV-chipkaart decoder: main program
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#        
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License at http://www.gnu.org/licenses/gpl.txt
# By using, editing and/or distributing this software you agree to
# the terms and conditions of this license.
#
# (c)2010 by Willem van Engen <dev-rfid@willem.engen.nl>
#
import sys

from ovc import *
from ovc.ovctypes import *
from ovc.util import mfclassic_getsector, getbits, mfclassic_getoffset


if __name__ == '__main__':

	if len(sys.argv) < 2:
		sys.stderr.write('Usage: %s <ovc_dump> [<ovc_dump_2> [...]]\n'%sys.argv[0])
		sys.exit(1)

	for fn in sys.argv[1:]:
		inp = open(fn, 'rb')
		data = inp.read()
		inp.close()

		if len(data) == 4096:	# mifare classic 4k
			# card details
			# TODO make the card an object in itself with fixed-position templates
			# note that these data areas are not yet fully understood
			cardid = getbits(data[0:4], 0, 4*8)
			cardtype = OvcCardType(getbits(data[0x10:0x36], 18*8+4, 19*8))
			validuntil = OvcDate(getbits(data[0x10:0x36], 11*8+6, 13*8+4))
			s = 'OV-Chipkaart id %d, %s, valid until %s'%(cardid, cardtype, validuntil)
			if cardtype==2:
				birthdate = OvcBcdDate(getbits(mfclassic_getsector(data, 22), 14*8, 18*8))
				s += ', birthdate %s'%birthdate
			print s

			# subscriptions
			print "Subscriptions:"
			for sector in range(32, 35):
				sdata = mfclassic_getsector(data, sector)[:-0x10]
				offset,size = mfclassic_getoffset(sector)
				for chunk in range(0, len(sdata), 0x30):
					if ord(sdata[chunk]) == 0: continue
					sys.stdout.write(('%03x: ' % (offset + chunk)))
					print OvcClassicTransaction(sdata[chunk:chunk+0x30])
			# transactions
			print "Transaction logs:"
			# Entries  0-10: for User, chronologic, may be erased?
			# Entries 11-23: for Conductor, not chronologic, only one check-in
			# Entries 24-27: add Credit transactions
			start_log_0 = 0
			start_log_1 = 11
			start_log_2 = 24
			log_entry = 0
			for sector in range(35, 39):
				sdata = mfclassic_getsector(data, sector)[:-0x10]
				offset,size = mfclassic_getoffset(sector)
				for chunk in range(0, len(sdata), 0x20):
					if (chunk + 0x20) > len(sdata): continue	# last few bytes, not big enough
					l = log_entry
					log_entry += 1
					if l == start_log_1 or l == start_log_2: print "--"
					if ord(sdata[chunk]) == 0: continue
					if   l >= start_log_2: l = l - start_log_2
					elif l >= start_log_1: l = l - start_log_1
					sys.stdout.write(('#%x=%03x: ' % (l, offset + chunk)))
					print OvcClassicTransaction(sdata[chunk:chunk+0x20])

			# saldo
			class OvcSaldoTransaction(OvcRecord):
				_fieldchars = [
					('id',     'I',   12, OvcTransactionId),
					('idsaldo','H',   12, OvcSaldoTransactionId),
					('saldo',  'N',   16, OvcAmountSigned),
					('unkU',   'U', None, FixedWidthHex),
					('unkV',   'V', None, FixedWidthHex),
				]
				_templates = [
					('20 II I0 00 00 00 80 HH H0 0N NN N0', {'I':1, 'N':1}),
				]
				def __str__(self):
					s = '[saldo_%02x__] '%(ord(self.data[0]))
					return s + OvcRecord.__str__(self)
				
			print "Credit:"
			sdata = mfclassic_getsector(data, 39)[:-0x10]
			offset,size = mfclassic_getoffset(39)
			for chunk in [0x90, 0xa0]:
				if ord(sdata[chunk]) == 0: continue
				sys.stdout.write(('%03x: ' % (offset + chunk)))
				print OvcSaldoTransaction(sdata[chunk:chunk+0x10])
			# indexes at FB0, FD0
			class OvcIndex(OvcRecord):
				_fieldchars = [
					('counter', 'I', 12, OvcTransactionId),
					('trans-ptr', 'J', 4, TransactionAddr),
				 	('unkY',   'Y', None , FixedWidthHex),
					('lstV',   'V', 28  , FixedWidthHex),
					('lstW',   'W', 48  , FixedWidthHex),
					('lstX',   'X', 48  , FixedWidthHex),
					# trans-ptr J is the first element of lstU
					('lstU',   'U', 36,   FixedWidthHex),
				 	('lstP',   'P', 48  , FixedWidthHex),
				 	('unkZ',   'Z', 12  , FixedWidthHex),
				    ]
				_templates = [
# 0fb0  a3 00 00 00 01 23 45 60 12 34 56 78 9a b0 12 34.56 78 9a b0 12 34 56 78 90 12 34 56 78 9a b1 00 
      ('PP PP II YY VV VV VV VW WW WW WW WW WW WX XX XX XX XX XX XJ UU UU UU UU UP PP PP PP PP PP PZ ZZ', {'I': -2, }),
				]
				def __str__(self):
					s = '[index_____] '
					return s + OvcRecord.__str__(self)
			print "Main index (current and previous):"
			# FB0, FD0
			#sdata = mfclassic_getsector(data, 39)[:-0x10]
			#offset,size = mfclassic_getoffset(39)
			for chunk in [0xb0, 0xd0]:
				sys.stdout.write(('%03x: ' % (offset + chunk)))
				print OvcIndex(sdata[chunk:chunk+0x20])

		elif len(data) == 64:	# mifare ultralight GVB
			# TODO card id, otp, etc.
			for chunk in range(0x10, len(data)-0x10, 0x10):
				# skip empty slots
				if data[chunk:chunk+2] == '\xff\xff': continue
				# print data
				t = OvcULTransaction(data[chunk:chunk+0x10])
				t.company = OvcCompany(2)
				print t

		else:
			sys.stderr.write('%s: expected 4096 or 64 bytes of ov-chipkaart dump file\n'%fn)
			sys.exit(2)

