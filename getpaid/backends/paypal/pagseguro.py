#-*- coding: utf-8 -*-
from django.conf import settings
from django.template.loader import render_to_string

from signals import PagSeguroSignal

import urllib
import urllib2
import time


PAGSEGURO_EMAIL_COBRANCA = settings.PAGSEGURO_EMAIL_COBRANCA
PAGSEGURO_TOKEN = settings.PAGSEGURO_TOKEN
PAGSEGURO_ERRO_LOG = getattr(settings, 'PAGSEGURO_ERRO_LOG', '')


class ItemPagSeguro(object):
    """
    ItemPagSeguro é usado no CarrinhoPagSeguro para representar
    cada Item de compra.

    O frete e o valor são convertidos para formato exigido para o PagSeguro.
    Regra do PagSeguro: valor real * 100.
        Dinheiro     Decimal/Float       PagSeguro
        R$ 1,50      1.50                150
        R$ 32,53     32.53               3253
    """
    def __init__(self, cod, descr, quant, valor, frete=0, peso=0):
        """
        O parâmetro cod deve ser único por CarrinhoPagSeguro

        Os parâmetros frete e peso são opcionais, os outros são
        obrigatórios
        """
        self.cod = cod
        self.descr = descr
        self.quant = quant
        self._valor = valor
        self._frete = frete
        self.peso = peso

    @property
    def frete(self):
        return int(self._frete * 100)

    @property
    def valor(self):
        return int(self._valor * 100)


class CarrinhoPagSeguro(object):
    """
    CarrinhoPagSeguro deve ser criado para gerar o Form para o PagSeguro.

    As configurações do carrinho, cliente e itens do pedido são definidas
    usando esta classe.

    Os atributos de configuração geral do carrinho são feitas no atributo
    self.config, os possíveis atributos podem ser encontrados na documentação
    oficial do PagSeguro:
        https://pagseguro.uol.com.br/desenvolvedor/carrinho_proprio.jhtml#rmcl

    Configurações de clientes deve ser feita através do método set_cliente.

    Para adicionar Items ao carrinho use método add_item.

    Para obter o HTML do Form do PagSeguro com o botão de Comprar use
    o método form.
    """
    def __init__(self, email_cobranca=PAGSEGURO_EMAIL_COBRANCA, **kwargs):
        """
        Cria o CarrinhoPagSeguro com dados iniciais baseado na documentação oficial
        do PagSeguro.

        A constante settings.PAGSEGURO_EMAIL_COBRANCA deve ser configurada com o email
        usado na sua conta do PagSeguro.
        """
        self.cliente = {}
        self.itens = []
        self.config = {
            'tipo' : 'CP',
            'moeda': 'BRL',
            'encoding': 'UTF-8',
            'email_cobranca': email_cobranca,
            'ref_transacao': '',
        }
        self.config.update(kwargs)

    def set_cliente(self, **kwargs):
        """
        Define as configurações do cliente, essas informações são opcionais,
        mas se tiver essa informações é interessante defini-las para facilitar
        para o cliente no site do PagSeguro.

        Os campos válidos são: nome, cep, end, num, compl, bairro, cidade, uf, pais,
        ddd, tel, email

        IMPORTANTE: Todos os valores devem ser passados como parâmetros nomeados.
        """
        campos_validos = ['nome', 'cep', 'end', 'num', 'compl',
                          'bairro', 'cidade', 'uf', 'pais',
                          'ddd', 'tel', 'email' ]
        kwargs = dict((k, v) for k, v in kwargs.items() if k in campos_validos)
        self.cliente.update(kwargs)

    def add_item(self, item):
        """
        Adiciona um novo ItemPagSeguro ao carrinho.

        Para mais informações consulte a documentação da classe ItemPagSeguro
        """
        self.itens.append(item)

    def form(self, template='pagseguro_form.html'):
        """
        Realiza o render do formulário do PagSeguro baseado no template.

        Por padrão o template usado é 'django_pagaseguro/templates/pagseguro_form.html',
        porém é possível sobreescrever o template ou passar outro template que desejar
        como parâmetro.
        """
        form_str = render_to_string(template, vars(self))
        return form_str

    def __repr__(self):
        return "<CarrinhoPagSeguro - email:%s - %s itens>" % (self.config['email_cobranca'], len(self.itens))


def _req_pagseguro(params):
    """ Faz requisição de validação ao PagSeguro """
    
    params_encode = urllib.urlencode(params)
    headers = {
         "Content-Type" : "application/x-www-form-urlencoded; charset=ISO-8859-1",
        }
    req = urllib2.Request('https://pagseguro.uol.com.br/Security/NPI/Default.aspx/?' + params_encode, data="data", \
                        headers=headers)

    res = urllib2.urlopen(req)
    retorno = res.read()
    res.close()
    return retorno


def validar_dados(dados, token=PAGSEGURO_TOKEN, erro_log=PAGSEGURO_ERRO_LOG):
    """
    No retorno automático do PagSeguro essa funcão é responsável
    por validar os dados + token do PagSeguro e emitir o Sinais para
    as outras aplicações.

    Para mais informações sobre o retorno automático e validação do PagSeguro
    consulte:
        https://pagseguro.uol.com.br/desenvolvedor/retorno_automatico_de_dados.jhtml#rmcl

    Caso os dados não sejam verificados a função retorna False e se
    a constante PAGSEGURO_ERRO_LOG estiver definida com um arquivo de log, as informações
    são gravadas.


    A constante settings.PAGSEGURO_TOKEN deve ser configurada com TOKEN fornecido pelo
    PagSeguro.

    A constante settings.PAGSEGURO_ERRO_LOG é opcional e deve ser um arquivo com permissão de escrita,
    exemplo:
        PAGSEGURO_ERRO_LOG = '/tmp/pagseguro_erro.log'

    """
    params = dados.copy()
    params.update({
        'Comando': 'validar',
        'Token': token,
    })
    retorno = _req_pagseguro(params)
    if retorno == 'VERIFICADO':
        ps_aviso = PagSeguroSignal(dados)
        ps_aviso.send()
        return True
    else:
        if erro_log:
            f = open(erro_log, 'a')
            f.write("%s - dados: %s - retorno: %s\n" % (time.ctime(), params, retorno))
            f.close()
        return False
